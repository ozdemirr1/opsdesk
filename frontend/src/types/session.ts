import type { UserProfile } from './user';

export type Session = {
  accessToken: string;
  user: UserProfile;
};
