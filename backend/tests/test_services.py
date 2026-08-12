from v2.services import classify_sign_result, retry_delay


def test_classify_success():
    assert classify_sign_result("success")[0] == "success"
    assert classify_sign_result("您已签到")[0] == "success"


def test_classify_manual_failures_are_not_retried():
    assert classify_sign_result("validate required") == ("manual_required", "CAPTCHA_REQUIRED", False)
    assert classify_sign_result("请登录")[1:] == ("COOKIE_EXPIRED", False)


def test_retry_schedule_stops_after_four_attempts():
    assert [retry_delay(i) for i in range(1, 6)] == [5, 15, 45, 120, None]
