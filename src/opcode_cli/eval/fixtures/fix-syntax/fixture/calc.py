def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b + 1


def divide(a, b):
    if b == 0:
        raise ValueError("division by zero")
    return a / b
