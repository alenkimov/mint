from typing import Optional

from pydantic import Field

from twitter._capsolver.core.serializer import TaskSer


class WebsiteDataOptionsSer(TaskSer):
    websiteURL: str = Field(..., description="Address of a webpage with Captcha")
    websiteKey: Optional[str] = Field(None, description="Website key")


class ReCaptchaV3Ser(WebsiteDataOptionsSer):
    pageAction: str = Field(
        "verify",
        description="Widget action value."
        "Website owner defines what user is doing on the page through this parameter",
    )


class HCaptchaClassificationOptionsSer(TaskSer):
    queries: list[str] = Field(..., description="Base64-encoded images, do not include 'data:image/***;base64,'")
    question: str = Field(
        ..., description="Question ID. Support English and Chinese, other languages please convert yourself"
    )
