from typing import Annotated

from fastapi import Depends, Request

from apps.api.core.config import AppSettings


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.settings


AppSettingsDep = Annotated[AppSettings, Depends(get_app_settings)]
