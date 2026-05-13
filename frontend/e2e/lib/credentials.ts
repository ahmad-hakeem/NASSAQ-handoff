/**
 * Credential loader for the e2e suite.
 *
 * All credentials are sourced from environment variables — the spec
 * (Task #197) explicitly forbids inlining emails / passwords in the
 * spec files, page-object helpers, README, or commit messages. The
 * canonical source of truth for the underlying test accounts is
 * `TEST_CREDENTIALS.md` at the repo root; devs seed the env via a
 * gitignored `playwright.local.env` file (see `e2e/README.md`).
 *
 * If a credential is missing we throw a clear error so the suite
 * never silently skips.
 */

export type Credential = { email: string; password: string };

function readEnv(name: string): string {
  const value = process.env[name];
  if (!value || !value.trim()) {
    throw new Error(
      `Missing E2E credentials: env var ${name} is not set. ` +
        `See frontend/e2e/README.md for the seeding step (refer to TEST_CREDENTIALS.md by filename).`,
    );
  }
  return value.trim();
}

export function getItBootstrappedCredentials(): Credential {
  return {
    email: readEnv('E2E_IT_BOOTSTRAPPED_EMAIL'),
    password: readEnv('E2E_IT_BOOTSTRAPPED_PASSWORD'),
  };
}

export function getItPreBootstrapCredentials(): Credential {
  return {
    email: readEnv('E2E_IT_PRE_BOOTSTRAP_EMAIL'),
    password: readEnv('E2E_IT_PRE_BOOTSTRAP_PASSWORD'),
  };
}

export function getPrincipalCredentials(): Credential {
  return {
    email: readEnv('E2E_PRINCIPAL_EMAIL'),
    password: readEnv('E2E_PRINCIPAL_PASSWORD'),
  };
}

export function getMfaUserCredentials(): Credential & { recoveryCode: string } {
  return {
    email: readEnv('E2E_MFA_USER_EMAIL'),
    password: readEnv('E2E_MFA_USER_PASSWORD'),
    recoveryCode: readEnv('E2E_MFA_USER_RECOVERY_CODE'),
  };
}
