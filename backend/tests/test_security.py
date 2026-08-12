from types import SimpleNamespace

import bcrypt

from v2.security import hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong", first)


def test_legacy_sha256_password_is_accepted_for_migration():
    assert verify_password("123", "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3")
