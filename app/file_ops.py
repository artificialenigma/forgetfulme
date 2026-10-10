"""Linux no-overwrite rename, anchored to directories that cannot be symlinks."""
import ctypes
import errno
import os
from pathlib import Path


def directory_fd(path):
    parts=Path(path).absolute().parts
    fd=os.open(parts[0],os.O_RDONLY|os.O_DIRECTORY)
    try:
        for component in parts[1:]:
            child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        return fd
    except BaseException:
        os.close(fd);raise


def rename_no_replace(source,destination):
    # RENAME_NOREPLACE is an atomic filesystem operation; never fall back to
    # link+unlink, which can delete an editor's concurrently replaced source.
    # Contract: https://man7.org/linux/man-pages/man2/rename.2.html
    libc=ctypes.CDLL(None,use_errno=True)
    function=getattr(libc,'renameat2',None)
    if function is None:
        raise OSError(errno.ENOTSUP,'Atomic no-overwrite rename is unavailable')
    function.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
    function.restype=ctypes.c_int
    source=Path(source);destination=Path(destination)
    oldfd=directory_fd(source.parent)
    try:
        newfd=directory_fd(destination.parent)
        try:
            if function(oldfd,os.fsencode(source.name),newfd,os.fsencode(destination.name),1):
                code=ctypes.get_errno();raise OSError(code,os.strerror(code))
            os.fsync(oldfd);os.fsync(newfd)
        finally:os.close(newfd)
    finally:os.close(oldfd)
