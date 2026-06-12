class LeadProcessingError(Exception):
    """Base error during lead processing."""


class FormNotFilledError(LeadProcessingError):
    """Form could not be filled or submitted."""


class LeadNotFoundError(LeadProcessingError):
    """Lead not found in InConcert within timeout."""


class InConcertAuthError(LeadProcessingError):
    """Login to InConcert failed."""


class ScreenshotUploadError(LeadProcessingError):
    """Screenshot could not be uploaded to Drive."""


class SheetsWriteError(LeadProcessingError):
    """Could not write result to Google Sheets."""


class CountryNotFoundError(ValueError):
    """Country not found in configuration."""


class OrchestratorCancelled(Exception):
    """Process was cancelled by user."""
