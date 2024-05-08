from twitter._capsolver.core.enum import MyEnum


class ReCaptchaV2TypeEnm(str, MyEnum):
    # V2
    ReCaptchaV2Task = "ReCaptchaV2Task"
    ReCaptchaV2EnterpriseTask = "ReCaptchaV2EnterpriseTask"
    ReCaptchaV2TaskProxyLess = "ReCaptchaV2TaskProxyLess"
    ReCaptchaV2EnterpriseTaskProxyLess = "ReCaptchaV2EnterpriseTaskProxyLess"


class ReCaptchaV3TypeEnm(str, MyEnum):
    ReCaptchaV3Task = "ReCaptchaV3Task"
    ReCaptchaV3EnterpriseTask = "ReCaptchaV3EnterpriseTask"
    ReCaptchaV3TaskProxyLess = "ReCaptchaV3TaskProxyLess"
    ReCaptchaV3EnterpriseTaskProxyLess = "ReCaptchaV3EnterpriseTaskProxyLess"


class HCaptchaTypeEnm(str, MyEnum):
    HCaptchaTask = "HCaptchaTask"
    HCaptchaTaskProxyless = "HCaptchaTaskProxyless"
    HCaptchaEnterpriseTask = "HCaptchaEnterpriseTask"
    HCaptchaEnterpriseTaskProxyLess = "HCaptchaEnterpriseTaskProxyLess"
    HCaptchaTurboTask = "HCaptchaTurboTask"
    HCaptchaClassification = "HCaptchaClassification"


class HCaptchaClassificationTypeEnm(str, MyEnum):
    HCaptchaClassification = "HCaptchaClassification"
