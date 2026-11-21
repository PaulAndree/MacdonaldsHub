from typing import Literal

Role = Literal["administrator", "global_manager"]
ROLES: tuple[Role, ...] = ("administrator", "global_manager")
