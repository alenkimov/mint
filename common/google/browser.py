import re
from functools import wraps
from typing import Literal

from yarl import URL
from undetected_playwright.async_api import (
    BrowserContext,
    Request,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

from .errors import (
    CaptchaRequired,
    FailedToOAuth2,
    FailedToLogin,
    BadLoginCookies,
    RecoveryRequired,
    RecoveryEmailRequired,
    TotpSecretRequired,
    PhoneVerificationRequired,
)
from .account import Account, AccountStatus
from .utils import check_cookies


PromptType = Literal["consent", "select_account"] | None


def are_valid_google_cookies(cookies: list[dict]) -> bool:
    """
    SID и HSID: Эти cookie содержат цифровые подписи и информацию о последнем входе в систему.
    SSID, APISID, SAPISID: Также содержат информацию об аутентификации и используются в различных сервисах Google для поддержания сессии пользователя.
    __Secure*: Хотя они в первую очередь используются для рекламных целей, они также связаны с твоей учетной записью и могут содержать важную информацию о сессии.
    NID: Используется для хранения настроек пользователя и может содержать информацию, упрощающую доступ к аккаунту.
    GAPS: Этот cookie используется для аутентификации в различных приложениях Google и может содержать важные данные аутентификации.

    Все cookie, содержащие информацию об аутентификации:
        SID
        HSID
        SSID
        APISID
        SAPISID
        OTZ
        NID
        OSID
        LSID
        SIDCC
        ACCOUNT_CHOOSER
        __Secure-1PSIDTS
        __Secure-3PSIDTS
        __Secure-1PSID
        __Secure-3PSID
        __Secure-1PAPISID
        __Secure-3PAPISID
        __Secure-1PSIDCC
        __Secure-3PSIDCC
        __Secure-OSID
        __Host-1PLSID
        __Host-3PLSID
        __Host-GAPS
    """
    return check_cookies(cookies, {"SID", "HSID"})


class GooglePlaywrightBrowserContext:
    # Common
    _RECAPTCHA_IFRAME_XPATH = '//iframe[@title="reCAPTCHA"]'
    _RECAPTCHA_CHECKBOX_CHECKED_XPATH = '//span[contains(@class, "recaptcha-checkbox-checked")]'
    _LEFT_BUTTON_XPATH = '//div[@jsname="QkNstf"]/div/div/button'  # Not now, Try another way
    _RIGHT_BUTTON_XPATH = '//div[@jsname="Njthtb"]/div/button'  # Continue, Send, Next
    # _ERRORS_COUNT_XPATH = '//div[@jsname="B34EJ"]'

    # Logining
    _EMAIL_FIELD_XPATH = '//*[@id="identifierId"]'
    _EMAIL_CONFIRMATION_BUTTON_XPATH = '//*[@id="identifierNext"]/div/button'
    _PASSWORD_FIELD_XPATH = '//*[@id="password"]/div[1]/div/div[1]/input'
    _PASSWORD_CONFIRMATION_BUTTON_XPATH = '//*[@id="passwordNext"]/div/button'
    _RECOVERY_EMAIL_BUTTON_XPATH = '//div[@data-challengeid="5"]'
    _RECOVERY_EMAIL_FIELD_XPATH = '//input[@id="knowledge-preregistered-email-response"]'
    _RECOVERY_BUTTON_XPATH = '//div[@id="accountRecoveryButton"]/div/div/a'
    _TOTP_FIELD_XPATH = '//input[@id="totpPin"]'

    # Logining: patterns
    _RECOVERY_REQUIRED_URL_PATTERN = re.compile(r"https://accounts\.google\.com/v3/signin/rejected.*")
    _PASSKEY_URL_PATTERN = re.compile(r"https://accounts\.google\.com/signin/v2/passkeyenrollment.*")
    _MY_ACCOUNT_URL_PATTERN = re.compile(r"https://myaccount\.google\.com.*")
    _GDS_URL_PATTERN = re.compile(r"https://gds\.google\.com.*")
    _LOGGED_IN_URL_PATTERNS = (_MY_ACCOUNT_URL_PATTERN, _GDS_URL_PATTERN)

    # OAuth2
    _CONTINUE_BUTTON_XPATH = '//div[@jsname="uRHG6"]/div/button'
    _ACCOUNT_BUTTON_XPATH = '//*[@data-identifier="{email}"]'

    # Phone
    _PHONE_NUMBER_INPUT_FIELD_XPATH = '//input[@id="deviceAddress"]'
    _COUNTRY_SELECT_MENU_XPATH = '//select[@id="countryList"]'
    _CODE_INPUT_FIELD = '//*[@id="smsUserPin"]'
    _NEXT_BUTTON_XPATH = '//*[@id="next-button"]'
    _ERROR_SPAN_XPATH = '//span[@id="error"]'

    def __init__(
            self,
            context: BrowserContext,
            account: Account,
            *,
            time_to_wait: int = 10_000,
            wait_for_captcha_solving: bool = True,
            time_to_solve_captcha: int = 30_000,
    ):
        self._context = context
        self.account = account
        self.time_to_wait = time_to_wait
        self.wait_for_captcha_solving = wait_for_captcha_solving
        self.time_to_solve_captcha = time_to_solve_captcha

        self._logged_in: bool = False

    @staticmethod
    async def close_page_on_error(fn):
        @wraps
        async def wrapper(page: Page, *args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            # except (PlaywrightTimeoutError, PlaywrightError):
            #     raise
            finally:
                await page.close()
        return wrapper

    def _account_button_xpath(self) -> str:
        return self._ACCOUNT_BUTTON_XPATH.format(email=self.account.email.lower())

    async def _location_href(self, page) -> str:
        return await page.evaluate("location.href")

    def logged_in(self) -> bool:
        return self._logged_in

    async def _type_password_with_confirmation(self, page: Page):
        password_input_field = page.locator(self._PASSWORD_FIELD_XPATH)
        password_confirmation_button = page.locator(self._PASSWORD_CONFIRMATION_BUTTON_XPATH)

        # Иногда пароль не печатается с первого раза по неизвестной причине
        while True:
            await password_input_field.type(self.account.password)
            password_input_field_value = await password_input_field.input_value()
            if password_input_field_value: break

        await password_confirmation_button.click()

    async def _check_and_pass_totp(self, page: Page):
        needs_totp = False
        totp_input_field = page.locator(self._TOTP_FIELD_XPATH)

        try:
            await totp_input_field.wait_for(timeout=self.time_to_wait)
            needs_totp = True
        except PlaywrightTimeoutError:
            pass

        if needs_totp:
            if not self.account.totp_secret:
                self.account.status = AccountStatus.TOTP_SECRET_REQUIRED
                raise TotpSecretRequired(f"Failed to login Google account: TOTP secret required.")

            # TODO Есть вероятность, что не успеет ввести код. Проверять время или делать повторную попытку
            await totp_input_field.type(self.account.get_totp_code())
            await page.locator(self._RIGHT_BUTTON_XPATH).click()

    async def _check_verification(self, page: Page):
        """
        Если в аккаунт с этого IP не входили ранее, то просит ввести totp или recovery_email.
        Также может попросить recovery_email после прохождения капчи, что будет означать, что аккаунт мертв.

        https://accounts.google.com/v3/signin/challenge/selection
        """
        needs_totp = False
        totp_input_field = page.locator(self._TOTP_FIELD_XPATH)

        try:
            await totp_input_field.wait_for(timeout=self.time_to_wait)
            needs_totp = True
        except PlaywrightTimeoutError:
            pass

        if needs_totp:

            if not self.account.totp_secret:
                self.account.status = AccountStatus.TOTP_SECRET_REQUIRED
                raise TotpSecretRequired(f"Failed to login Google account: totp secret required.")

            # TODO Есть вероятность, что не успеет ввести код. Проверять время или делать повторную попытку
            await page.locator(self._TOTP_FIELD_XPATH).type(self.account.get_totp_code())
            await page.locator(self._RIGHT_BUTTON_XPATH).click()

        else:
            needs_recovery_email = False
            recovery_email_button = page.locator(self._RECOVERY_EMAIL_BUTTON_XPATH)

            try:
                await recovery_email_button.wait_for(timeout=self.time_to_wait)
                needs_recovery_email = True
            except PlaywrightTimeoutError:
                pass

            if needs_recovery_email:
                if not self.account.recovery_email:
                    self.account.status = AccountStatus.RECOVERY_EMAIL_REQUIRED
                    raise RecoveryEmailRequired(f"Failed to login Google account: recovery email required.")

                await recovery_email_button.click()
                await page.wait_for_load_state("load")

                recovery_input_field = page.locator(self._RECOVERY_EMAIL_FIELD_XPATH)
                # Иногда Recovery Email не печатается с первого раза по неизвестной причине
                while True:
                    await recovery_input_field.type(self.account.recovery_email)
                    recovery_input_field_value = await recovery_input_field.input_value()
                    if recovery_input_field_value: break
                await page.locator(self._RIGHT_BUTTON_XPATH).click()

            await page.wait_for_load_state("load")

            try:
                await page.locator(self._RECOVERY_BUTTON_XPATH).wait_for(timeout=self.time_to_wait)
                self.account.status = AccountStatus.RECOVERY_REQUIRED
                raise RecoveryRequired("Failed to login Google account."
                                       " Google: We noticed unusual activity in your Google Account."
                                       " To keep your account safe, you were signed out."
                                       " To continue, you’ll need to verify it’s you.")
            except PlaywrightTimeoutError:
                pass

        await page.wait_for_load_state("load")

        # https://accounts.google.com/v3/signin/challenge
        # To help keep your account safe, Google wants to make sure it’s really you trying to sign in
        # Open a browser on a phone or computer where you’re already signed in and go to:
        # https://g.co/verifyaccount
        if (await page.locator(self._LEFT_BUTTON_XPATH).count() > 0
                and await page.locator(self._RIGHT_BUTTON_XPATH).count() == 0):
            raise RecoveryRequired("Failed to login Google account."
                                   " Google: To help keep your account safe, Google wants to make sure it’s really you trying to sign in"
                                   " Open a browser on a phone or computer where you’re already signed in and go to:"
                                   " https://g.co/verifyaccount")

    async def _check_phone_verification(self, page: Page):
        # country_select_menu = page.locator(self._COUNTRY_SELECT_MENU_XPATH)
        # phone_number_input_field = page.locator(self._PHONE_NUMBER_INPUT_FIELD_XPATH)
        # code_input_field = page.locator(self._CODE_INPUT_FIELD)
        # next_button = page.locator(self._NEXT_BUTTON_XPATH)
        # error_span = page.locator(self._ERROR_SPAN_XPATH)

        if "https://accounts.google.com/speedbump/idvreenable" in await self._location_href(page):
            self.account.status = AccountStatus.PHONE_VERIFICATION_REQUIRED
            raise PhoneVerificationRequired("Phone verification required.")

    async def _check_captcha_and_type_password(self, page: Page, login: bool = True):
        recaptcha_iframe = page.locator(self._RECAPTCHA_IFRAME_XPATH)
        await page.wait_for_load_state("networkidle")
        try:
            await recaptcha_iframe.wait_for(timeout=self.time_to_wait)
            self.account.status = AccountStatus.CAPTCHA_REQUIRED
        except PlaywrightTimeoutError:
            pass

        if self.account.status == AccountStatus.CAPTCHA_REQUIRED:
            if self.wait_for_captcha_solving:
                try:
                    recaptcha_frame_name = await recaptcha_iframe.get_attribute("name")
                    recaptcha = page.frame(name=recaptcha_frame_name)
                    await recaptcha.locator(self._RECAPTCHA_CHECKBOX_CHECKED_XPATH).wait_for(
                        timeout=self.time_to_solve_captcha)
                    await page.locator(self._RIGHT_BUTTON_XPATH).click()
                    await self._type_password_with_confirmation(page)
                    await self._check_verification(page)
                    await self._check_phone_verification(page)
                    return
                except PlaywrightTimeoutError:
                    pass
            raise CaptchaRequired("Failed to login Google account: captcha required.")
        elif login:
            await self._type_password_with_confirmation(page)
            await self._check_verification(page)

    async def _login_with_password(self, page: Page):
        try:
            await page.goto("https://accounts.google.com/ServiceLogin")
            await page.locator(self._EMAIL_FIELD_XPATH).type(self.account.email)
            await page.locator(self._EMAIL_CONFIRMATION_BUTTON_XPATH).click()
            await self._check_captcha_and_type_password(page)

            # Иногда просит установить passkey
            if self._PASSKEY_URL_PATTERN.search(page.url):
                # Not now button
                await page.locator(self._LEFT_BUTTON_XPATH).click(timeout=self.time_to_wait)

            await page.wait_for_load_state("load")

            cookies = None
            for _ in range(5):
                await page.wait_for_timeout(self.time_to_wait / 5)
                if any(url_pattern.search(page.url) for url_pattern in self._LOGGED_IN_URL_PATTERNS):
                    cookies = await self._context.cookies()
                    self._logged_in = are_valid_google_cookies(cookies)
                    break

            if self._logged_in:
                self.account.status = AccountStatus.GOOD
                self.account.cookies = cookies
            else:
                self.account.status = AccountStatus.UNKNOWN
                raise FailedToLogin("Failed to login Google account: failed to catch auth cookies.")
        except PlaywrightTimeoutError:
            raise FailedToLogin("Failed to login Google account: unexpected TimeoutError.")
        except PlaywrightError as exc:
            raise FailedToLogin(f"Failed to login Google account: {exc}")

    async def _set_login_cookies(self, cookies: list[dict]):
        if not are_valid_google_cookies(cookies):
            raise BadLoginCookies(f"Bad login cookies!")

        await self._context.add_cookies(cookies)
        self._logged_in = True

    async def _login(
            self,
            page: Page,
    ):
        if self._logged_in:
            return

        if self.account.cookies:
            try:
                await self._set_login_cookies(self.account.cookies)
                return
            except BadLoginCookies:
                pass

        await self._login_with_password(page)

    async def login(self):
        page = await self._context.new_page()
        await self._login(page)
        await page.close()

    async def _oauth2(
            self,
            page: Page,
            *,
            client_id: str,
            redirect_uri: str,
            scope: str,
            gsiwebsdk: int = 3,
            access_type: str = "offline",
            response_type: str = "code",
            prompt: PromptType = None,
            include_granted_scopes: bool | str = True,
            enable_granular_consent: bool | str = True,
    ) -> tuple[str, str]:
        """
        :return: oauth_code, redirect_url
        """
        oauth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "gsiwebsdk": gsiwebsdk,
            "access_type": access_type,
            "response_type": response_type,
            "include_granted_scopes": str(include_granted_scopes).lower(),
            "enable_granular_consent": str(enable_granular_consent).lower(),
        }
        if prompt: params["prompt"] = prompt
        oauth_url = str(URL(oauth_url).with_query(params))

        oauth_code = None
        redirect_url = None

        async def request_handler(request: Request):
            nonlocal oauth_code
            nonlocal redirect_url

            # Поимка oauth_code и redirect_url основана на знании того, что гугл делает такой редирект:
            # https://developers.google.com/identity/protocols/oauth2/javascript-implicit-flow#redirecting
            if request.url.startswith(redirect_uri):
                redirect_url = URL(request.url)
                oauth_code = redirect_url.query.get(response_type)

        page.on("request", request_handler)

        try:
            await page.goto(oauth_url)
            # TODO Поведение страницы может отличаться, если значение prompt != "consent"
            await page.wait_for_timeout(self.time_to_wait)
            await page.locator(self._account_button_xpath()).click()
            await self._check_and_pass_totp(page)
            await self._check_captcha_and_type_password(page, login=False)
            try:
                await page.locator(self._CONTINUE_BUTTON_XPATH).click(timeout=self.time_to_wait)
            except PlaywrightTimeoutError:
                pass
            await page.wait_for_timeout(self.time_to_wait)
        except PlaywrightTimeoutError:
            raise FailedToOAuth2("Failed to OAuth2 Google account: unexpected TimeoutError.")
        except PlaywrightError as exc:
            raise FailedToOAuth2(f"Failed to OAuth2 Google account: {exc}")

        if not oauth_code:
            raise FailedToOAuth2("Failed to OAuth2 Google account: Failed to catch oauth code.")

        return oauth_code, str(redirect_url)

    async def oauth2(self, **oauth2_params) -> tuple[str, str]:
        """
        Найдите подобную ссылку: `https://accounts.google.com/o/oauth2/v2/auth?client_id=...`
        Передайте параметры ссылки (после знака вопроса (?)) в метод oauth2
        Метод вернет oauth_code и redirect_url (также содержится в redirect_url)
        :return: oauth_code, redirect_url
        """
        page = await self._context.new_page()
        try:
            await self._login(page)
            oauth_code, redirect_url = await self._oauth2(page, **oauth2_params)
        finally:
            await page.close()
        return oauth_code, redirect_url
