// ============================================================================
// User Model - DynamoDB store
// ============================================================================

import type { User } from '@terminal/shared';
import {
  createUserRecord,
  getUserById,
  getUserByEmail,
  userExistsByEmail,
  type UserRecord,
  KeyPrefix,
} from '../services/dynamodb';

export interface CreateUserData {
  id: string;
  email: string;
  displayName?: string;
}

export async function createUser(data: CreateUserData): Promise<User> {
  const now = Date.now();
  const userRecord: UserRecord = {
    PK: `${KeyPrefix.USER}${data.id}`,
    SK: KeyPrefix.PROFILE,
    GSI1PK: data.email.toLowerCase(),
    id: data.id,
    email: data.email,
    displayName: data.displayName,
    createdAt: now,
    updatedAt: now,
  };

  await createUserRecord(userRecord);

  return {
    id: userRecord.id,
    email: userRecord.email,
    displayName: userRecord.displayName,
    createdAt: userRecord.createdAt,
    updatedAt: userRecord.updatedAt,
  };
}

export async function findUserById(id: string): Promise<User | null> {
  return await getUserById(id);
}

export async function findUserByEmail(email: string): Promise<User | null> {
  return await getUserByEmail(email);
}

export async function userExists(email: string): Promise<boolean> {
  return await userExistsByEmail(email);
}

export function toPublicUser(user: User): User {
  return {
    id: user.id,
    email: user.email,
    displayName: user.displayName,
    createdAt: user.createdAt,
    updatedAt: user.updatedAt,
  };
}
