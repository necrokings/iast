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
  passwordHash: string;
}

export async function createUser(data: CreateUserData): Promise<User> {
  const now = Date.now();
  const userRecord: UserRecord = {
    PK: `${KeyPrefix.USER}${data.id}`,
    SK: KeyPrefix.PROFILE,
    GSI1PK: data.email.toLowerCase(),
    id: data.id,
    email: data.email,
    passwordHash: data.passwordHash,
    createdAt: now,
    updatedAt: now,
  };

  await createUserRecord(userRecord);

  return {
    id: userRecord.id,
    email: userRecord.email,
    createdAt: userRecord.createdAt,
    updatedAt: userRecord.updatedAt,
  };
}

export async function findUserById(id: string): Promise<(User & { passwordHash: string }) | null> {
  return await getUserById(id);
}

export async function findUserByEmail(
  email: string
): Promise<(User & { passwordHash: string }) | null> {
  return await getUserByEmail(email);
}

export async function userExists(email: string): Promise<boolean> {
  return await userExistsByEmail(email);
}

export function toPublicUser(user: User & { passwordHash: string }): User {
  return {
    id: user.id,
    email: user.email,
    createdAt: user.createdAt,
    updatedAt: user.updatedAt,
  };
}

// ============================================================================
// Demo User - Create on startup
// ============================================================================

async function createDemoUser(): Promise<void> {
  const demoEmail = 'demo@example.com';
  const demoPassword = 'demo1234';

  if (await userExists(demoEmail)) {
    return;
  }

  // Hash password with bcrypt (10 rounds)
  const bcrypt = await import('bcrypt');
  const passwordHash = await bcrypt.hash(demoPassword, 10);

  await createUser({
    id: 'demo-user-001',
    email: demoEmail,
    passwordHash,
  });

  console.log('✓ Demo user created: demo@example.com / demo1234');
}

// Create demo user on module load
void createDemoUser();
