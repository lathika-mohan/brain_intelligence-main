import { z } from 'zod';

export const loginSchema = z.object({
  username: z.string().min(3, { message: 'Operational identification token must contain 3+ characters.' }),
  password: z.string().min(8, { message: 'Security credentials must contain 8+ characters.' }),
});
