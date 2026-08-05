export type UserRole = "viewer" | "operator" | "approver" | "admin";

export type MeResponse = {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
};

export type LoginResponse = {
  user: MeResponse;
};

export class AuthError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

export class SessionExpiredError extends AuthError {
  constructor(message = "Session expired. Please sign in again.") {
    super(message, 401);
    this.name = "SessionExpiredError";
  }
}
