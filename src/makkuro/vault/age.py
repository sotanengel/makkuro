"""age-encrypted persistent vault (spec F5).

The on-disk format is a single age-encrypted blob; the plaintext inside
is a JSON object ``{placeholder: original}``. Writes are atomic (write a
sibling tempfile then ``os.replace``).

Usage sketch::

    identity = AgeVault.load_identity(Path("~/.config/makkuro/identity.txt"))
    vault = AgeVault.open(Path("~/.local/share/makkuro/vault.age"), identity)
    vault.put(placeholder, original)
    vault.save()  # re-encrypts and writes the whole file

The vault's file permissions are strictly enforced (0600 for the vault
itself, 0700 for the directory) because the age identity file is the
only gate between a local attacker and plaintext secrets (spec §8 T03).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Avoid importing the optional dep at module-load time.
    from pyrage import x25519


class AgeVaultError(RuntimeError):
    pass


def _require_pyrage():
    try:
        import pyrage  # noqa: F401
    except ImportError as e:
        raise AgeVaultError(
            "age vault backend requires the `pyrage` package. "
            "Install it with `pip install makkuro[age]` (or `pip install pyrage`)."
        ) from e
    return __import__("pyrage", fromlist=["x25519"])


def _chmod_strict(path: Path, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError:
        # Windows / some filesystems silently ignore chmod. Not fatal.
        pass


def _check_perms(path: Path, required: int) -> None:
    """Refuse to read a keyfile that the OS reports as world-readable."""
    if os.name != "posix":
        return
    st = path.stat()
    if st.st_mode & 0o777 > required:
        raise AgeVaultError(
            f"{path} has permissions {oct(st.st_mode & 0o777)}; "
            f"required {oct(required)} or stricter"
        )


class AgeVault:
    """age-encrypted placeholder/original mapping with atomic writes."""

    def __init__(
        self,
        path: Path,
        identity: x25519.Identity,
        recipient: x25519.Recipient,
    ) -> None:
        self._path = path
        self._identity = identity
        self._recipient = recipient
        self._store: dict[str, str] = {}
        self._lock = threading.Lock()

    # ---- construction ----

    @classmethod
    def create(cls, path: Path, identity_path: Path) -> AgeVault:
        """Create a fresh identity + empty vault. Raises on overwrite."""
        pyrage = _require_pyrage()
        if path.exists():
            raise AgeVaultError(f"{path} already exists; refuse to overwrite")
        if identity_path.exists():
            raise AgeVaultError(
                f"{identity_path} already exists; refuse to overwrite"
            )

        identity = pyrage.x25519.Identity.generate()
        recipient = identity.to_public()

        identity_path.parent.mkdir(parents=True, exist_ok=True)
        _chmod_strict(identity_path.parent, 0o700)
        identity_path.write_text(str(identity) + "\n", encoding="utf-8")
        _chmod_strict(identity_path, 0o600)

        path.parent.mkdir(parents=True, exist_ok=True)
        _chmod_strict(path.parent, 0o700)

        vault = cls(path=path, identity=identity, recipient=recipient)
        vault.save()
        return vault

    @classmethod
    def load_identity(cls, identity_path: Path) -> x25519.Identity:
        pyrage = _require_pyrage()
        if not identity_path.exists():
            raise AgeVaultError(f"identity file {identity_path} not found")
        _check_perms(identity_path, 0o600)
        raw = identity_path.read_text(encoding="utf-8").strip()
        if not raw.startswith("AGE-SECRET-KEY-"):
            raise AgeVaultError(f"{identity_path} is not an age X25519 identity")
        return pyrage.x25519.Identity.from_str(raw)

    @classmethod
    def open(cls, path: Path, identity: x25519.Identity) -> AgeVault:
        pyrage = _require_pyrage()
        if not path.exists():
            raise AgeVaultError(f"vault file {path} does not exist")
        _check_perms(path, 0o600)
        ciphertext = path.read_bytes()
        try:
            plaintext = pyrage.decrypt(ciphertext, [identity])
        except Exception as e:  # pyrage wraps errors in Python exceptions
            raise AgeVaultError(f"decryption failed: {e}") from e
        try:
            data = json.loads(plaintext.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise AgeVaultError(f"vault payload is not JSON: {e}") from e
        recipient = identity.to_public()
        vault = cls(path=path, identity=identity, recipient=recipient)
        if isinstance(data, dict):
            vault._store = {str(k): str(v) for k, v in data.items()}
        return vault

    # ---- Vault protocol ----

    def put(self, placeholder: str, original: str) -> None:
        with self._lock:
            self._store[placeholder] = original

    def get(self, placeholder: str) -> str | None:
        with self._lock:
            return self._store.get(placeholder)

    def __contains__(self, placeholder: str) -> bool:
        with self._lock:
            return placeholder in self._store

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    # ---- persistence ----

    def save(self) -> None:
        pyrage = _require_pyrage()
        with self._lock:
            payload = json.dumps(self._store, ensure_ascii=False).encode("utf-8")
            ciphertext = pyrage.encrypt(payload, [self._recipient])
            # Atomic replace: write a sibling tempfile, fsync, then rename.
            parent = self._path.parent
            parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=".makkuro-vault-", suffix=".tmp", dir=str(parent)
            )
            try:
                with os.fdopen(fd, "wb") as h:
                    h.write(ciphertext)
                    h.flush()
                    os.fsync(h.fileno())
                _chmod_strict(Path(tmp_path), 0o600)
                os.replace(tmp_path, self._path)
            finally:
                # replace() succeeds => tmp_path no longer exists.
                # On failure we still want to clean up.
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

    def purge_all(self) -> None:
        with self._lock:
            self._store.clear()
        self.save()
