/** Payload embedded in the enrollment token (a JWT) issued by the API. */
export interface EnrollTokenPayload {
  /** installation id (the token `sub`) */
  sub?: string;
  installation_id?: string;
  device_name?: string;
  device_type?: string;
  hostname?: string;
  platform?: string;
  exp?: number;
}
