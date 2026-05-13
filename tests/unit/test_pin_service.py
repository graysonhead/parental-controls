from parental_controls.services.pin_service import hash_pin, verify_pin


def test_hash_and_verify_correct_pin():
    hashed = hash_pin("1234")
    assert verify_pin("1234", hashed) is True


def test_wrong_pin_does_not_verify():
    hashed = hash_pin("1234")
    assert verify_pin("0000", hashed) is False


def test_different_hashes_same_pin():
    h1 = hash_pin("1234")
    h2 = hash_pin("1234")
    # bcrypt generates different salts each time
    assert h1 != h2
    # But both verify correctly
    assert verify_pin("1234", h1) is True
    assert verify_pin("1234", h2) is True
