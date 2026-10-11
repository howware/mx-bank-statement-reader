"""Errores con código estable y código de salida de la CLI (ver docs/02 §3.3)."""

from __future__ import annotations


class MxBankError(Exception):
    code = "INTERNAL_ERROR"
    exit_code = 50

    def __init__(self, message: str, file: str | None = None, details: list | None = None):
        super().__init__(message)
        self.message = message
        self.file = file
        self.details = details  # nunca valores del documento: solo rutas/tipos

    def to_dict(self) -> dict:
        err = {"code": self.code, "exit_code": self.exit_code, "message": self.message}
        if self.file:
            err["file"] = self.file
        if self.details:
            err["details"] = self.details
        return {"ok": False, "error": err}


class UsageError(MxBankError):
    code, exit_code = "USAGE_ERROR", 2


class FileNotFound(MxBankError):
    code, exit_code = "FILE_NOT_FOUND", 10


class NotAPdf(MxBankError):
    code, exit_code = "NOT_A_PDF", 10


class PasswordRequired(MxBankError):
    code, exit_code = "PDF_PASSWORD_REQUIRED", 11


class NoText(MxBankError):
    code, exit_code = "PDF_NO_TEXT", 12


class BankNotRecognized(MxBankError):
    code, exit_code = "BANK_NOT_RECOGNIZED", 20


class LowConfidence(MxBankError):
    code, exit_code = "LOW_CONFIDENCE", 21


class Unbalanced(MxBankError):
    code, exit_code = "UNBALANCED", 30


class ResidualPII(MxBankError):
    code, exit_code = "RESIDUAL_PII_DETECTED", 40
