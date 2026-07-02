"""
ftp_client.py
=============
Cliente FTPS para conectarse a la plataforma de información de XM Colombia.
Maneja la conexión segura, descarga de archivos y manejo de errores.
"""

import ftplib
import io
import ssl
from typing import Optional, Tuple, List


class FTPSClient:
    """Cliente FTPS con soporte para modo explícito e implícito."""

    def __init__(self, host: str, user: str, password: str, port: int = 21):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.ftp: Optional[ftplib.FTP_TLS] = None
        self._connected = False

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def connect(self) -> Tuple[bool, str]:
        """
        Establece conexión FTPS (TLS explícito).
        Retorna (éxito: bool, mensaje: str).
        """
        try:
            # Contexto TLS permisivo para compatibilidad con servidores legacy
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            self.ftp = ftplib.FTP_TLS(context=ctx)
            self.ftp.connect(host=self.host, port=self.port, timeout=120)
            self.ftp.auth()                        # Iniciar TLS explícito
            self.ftp.login(self.user, self.password)
            self.ftp.prot_p()                      # Canal de datos cifrado
            self.ftp.set_pasv(True)                # Modo pasivo

            self._connected = True
            return True, f"✅ Conectado a {self.host}:{self.port} como '{self.user}'"

        except ftplib.error_perm as e:
            return False, f"❌ Error de credenciales: {e}"
        except ConnectionRefusedError:
            return False, f"❌ Conexión rechazada en {self.host}:{self.port}"
        except TimeoutError:
            return False, f"❌ Tiempo de espera agotado al conectar a {self.host}"
        except Exception as e:
            return False, f"❌ Error inesperado: {type(e).__name__}: {e}"

    def disconnect(self) -> None:
        """Cierra la conexión FTP de forma segura."""
        if self.ftp and self._connected:
            try:
                self.ftp.quit()
            except Exception:
                try:
                    self.ftp.close()
                except Exception:
                    pass
        self.ftp = None
        self._connected = False

    def is_connected(self) -> bool:
        """Verifica si la conexión está activa."""
        if not self._connected or self.ftp is None:
            return False
        try:
            self.ftp.voidcmd("NOOP")
            return True
        except Exception:
            self._connected = False
            return False

    # ------------------------------------------------------------------
    # Operaciones de directorio y archivos
    # ------------------------------------------------------------------

    def list_directory(self, path: str) -> Tuple[bool, List[str]]:
        """
        Lista los archivos en un directorio remoto.
        Retorna (éxito: bool, lista_archivos: List[str]).
        """
        if not self.is_connected():
            return False, []
        try:
            files = self.ftp.nlst(path)
            # Devolver solo el nombre del archivo, no la ruta completa
            return True, [f.split("/")[-1] for f in files]
        except ftplib.error_perm:
            return False, []
        except Exception:
            return False, []

    def download_file(self, remote_path: str) -> Optional[str]:
        """
        Descarga un archivo remoto y devuelve su contenido como string.
        Retorna None si el archivo no existe o hay error.

        Si la conexión se cayó (p.ej. timeout de inactividad del servidor
        durante una descarga larga de muchos archivos), reconecta con las
        mismas credenciales y reintenta la descarga una vez antes de darse
        por vencido.
        """
        if not self.is_connected() and not self.connect()[0]:
            return None

        buffer = io.BytesIO()
        try:
            self.ftp.retrbinary(f"RETR {remote_path}", buffer.write)
        except ftplib.error_perm:
            # Archivo no encontrado (error 550) — no es un problema de conexión
            return None
        except ftplib.error_temp:
            # Error temporal del servidor
            return None
        except (OSError, EOFError):
            # Conexión perdida durante la descarga → reconectar y reintentar una vez
            if not self.connect()[0]:
                return None
            buffer = io.BytesIO()
            try:
                self.ftp.retrbinary(f"RETR {remote_path}", buffer.write)
            except Exception:
                return None
        except Exception:
            return None

        buffer.seek(0)
        raw = buffer.read()

        # Intentar decodificar con múltiples encodings
        for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue

        return None

    def file_exists(self, remote_path: str) -> bool:
        """Verifica si un archivo existe en el servidor."""
        if not self.is_connected():
            return False
        try:
            self.ftp.size(remote_path)
            return True
        except ftplib.error_perm:
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False
