export class KeyManagerError extends Error {
  statusCode?: number;
  body?: unknown;

  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message);
    this.name = "KeyManagerError";
    this.statusCode = statusCode;
    this.body = body;
  }
}

export class AuthenticationError extends KeyManagerError {
  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "AuthenticationError";
  }
}

export class NotFoundError extends KeyManagerError {
  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "NotFoundError";
  }
}

export class ValidationErrorResponse extends KeyManagerError {
  errors: Record<string, unknown>[];

  constructor(message: string, errors: Record<string, unknown>[] = [], statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "ValidationError";
    this.errors = errors;
  }
}

export class RateLimitError extends KeyManagerError {
  retryAfter?: number;

  constructor(message: string, retryAfter?: number, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "RateLimitError";
    this.retryAfter = retryAfter;
  }
}

export class ServerError extends KeyManagerError {
  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "ServerError";
  }
}

export class ConnectionError extends KeyManagerError {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionError";
  }
}
