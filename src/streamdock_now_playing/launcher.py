"""Configurable launcher settings and Windows dispatch, independent of the LCD UI."""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class LauncherSettings:
    label: str = 'APP'
    target: str | None = None
    icon_path: str | None = None
    icon_only: bool = False

    @classmethod
    def from_config(cls, config):
        values={}
        for name in ('label','target','icon_path'):
            value=config.get(name)
            if value is not None and not isinstance(value,str):
                raise ValueError('Launcher '+name+' must be a string')
            values[name]=(value.strip() or None) if isinstance(value,str) else None
        icon_only=config.get('icon_only',False)
        if type(icon_only) is not bool:raise ValueError('Launcher icon_only must be a boolean')
        return cls(values['label'] or 'APP',values['target'],values['icon_path'],icon_only)

    @property
    def configured(self):return self.target is not None


def expand_target(value):
    return os.path.expandvars(os.path.expanduser(value))


def open_target(target):
    """Launch a user-configured file/shortcut/URI; never construct a shell command."""
    if not isinstance(target,str) or not target.strip():raise ValueError('Launcher target is not configured')
    if os.name!='nt':raise OSError('Application launch is Windows-only')
    os.startfile(expand_target(target))
