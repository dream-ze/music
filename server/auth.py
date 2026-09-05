from fastapi import Header, HTTPException

import config


def require_passcode(x_passcode: str = Header(default="")) -> str:
    """校验 X-Passcode。APP_PASSCODE 为空时放行(本地开发)。"""
    if not config.APP_PASSCODE:
        return "anonymous"
    if x_passcode != config.APP_PASSCODE:
        raise HTTPException(status_code=401, detail="口令错误")
    return x_passcode
