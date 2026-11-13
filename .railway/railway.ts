// The Railway project for every environment. plans/deploy.md explains the layout.
// Preview with `railway config plan --environment <name>`, then `railway config apply`.
// Variables are managed here: one missing from a service's env is deleted on apply, so a
// secret set in the dashboard is listed as preserve(), which keeps Railway's value.
import { defineRailway, github, postgres, preserve, project, redis, service, volume } from "railway/iac";

const REPO = "tvmaasjazz/personagora";
const REGION = "us-west2";

const ENVIRONMENTS = {
  staging: {
    branch: "main",
    environmentType: "STAGING",
    frontendDomain: "staging.personagora.com",
    apiDomain: "api-staging.personagora.com",
    areDomainsRegistered: true,
  },
  production: {
    branch: "production",
    environmentType: "PRODUCTION",
    frontendDomain: "personagora.com",
    apiDomain: "api.personagora.com",
    // The file can't register a custom domain, only keep one: add both with
    // `railway domain`, then set this to true (plans/deploy.md › Production)
    areDomainsRegistered: false,
  },
} as const;

export default defineRailway((ctx) => {
  const environmentName = ctx.environment as keyof typeof ENVIRONMENTS;
  const environment = ENVIRONMENTS[environmentName];
  if (environment === undefined) {
    throw new Error(`No Railway settings for the "${ctx.environment}" environment`);
  }
  const frontendUrl = `https://${environment.frontendDomain}`;

  const Postgres = postgres("Postgres", { region: REGION });
  Postgres.networking = { privateNetworkEndpoint: "postgres" };
  const postgresVolume = volume("postgres-volume", {
    alerts: { usage: { "100": {}, "80": {}, "95": {} } },
    allowOnlineResize: true,
    region: REGION,
    sizeMB: 50000,
  });

  // Redis 8 or later: the graph checkpointer needs its search module
  const Redis = redis("Redis", { region: REGION });
  Redis.deploy = {
    startCommand:
      '/bin/sh -c "rm -rf $RAILWAY_VOLUME_MOUNT_PATH/lost+found/ && exec docker-entrypoint.sh redis-server --requirepass $REDIS_PASSWORD --save 60 1 --dir $RAILWAY_VOLUME_MOUNT_PATH"',
  };
  Redis.networking = { privateNetworkEndpoint: "redis" };
  const redisVolume = volume("redis-volume", {
    alerts: { usage: { "100": {}, "80": {}, "95": {} } },
    allowOnlineResize: true,
    region: REGION,
    sizeMB: 50000,
  });

  const api = service("api", {
    source: github(REPO, { branch: environment.branch, checkSuites: true, rootDirectory: "/backend" }),
    // Railway builds from the Dockerfile it finds in the root directory
    build: { watchPatterns: ["/backend/**"] },
    preDeploy: "alembic upgrade head",
    healthcheck: "/health",
    healthcheckTimeout: 120,
    // One granian worker per instance; scale by instances
    replicas: { [REGION]: 2 },
    // Draining stays above the app's 150s shutdown drain
    deploy: { drainingSeconds: 180, overlapSeconds: 10, restartPolicyMaxRetries: 5 },
    domains: environment.areDomainsRegistered ? [{ domain: environment.apiDomain, port: 8000 }] : [],
    env: {
      ENVIRONMENT: environment.environmentType,
      // Granian's port is fixed in the Dockerfile, since exec form can't expand $PORT
      PORT: "8000",
      // asyncpg needs its own scheme, so the URL is built from Postgres's parts
      DATABASE_URL:
        "postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}",
      REDIS_URL: Redis.env.REDIS_URL,
      AUTH__FRONTEND_URL: frontendUrl,
      // Through the frontend's domain, so the session cookie lands where the browser is
      GOOGLE_AUTH__REDIRECT_URL: `${frontendUrl}/api/auth/google/callback`,
      // Cloudflare in front of Railway's edge (plans/deploy.md › How the browser reaches the API)
      USERS__CLIENT_IP_SOURCE: "CLOUDFLARE",
      GOOGLE_CLIENT_ID: preserve(),
      GOOGLE_CLIENT_SECRET: preserve(),
      OPENAI_API_KEY: preserve(),
    },
  });

  const web = service("web", {
    source: github(REPO, { branch: environment.branch, checkSuites: true, rootDirectory: "/frontend" }),
    // Railway builds from the Dockerfile it finds in the root directory
    build: { watchPatterns: ["/frontend/**"] },
    healthcheck: "/",
    replicas: { [REGION]: 1 },
    deploy: { restartPolicyMaxRetries: 5 },
    domains: environment.areDomainsRegistered
      ? [{ domain: environment.frontendDomain, port: 8080 }]
      : [],
    env: {
      PORT: "8080",
      // Caddy forwards /api/* here over the private network
      API_UPSTREAM: "${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}",
    },
  });

  return project("personagora", {
    variables: { managed: true },
    resources: [api, web, Postgres, Redis, postgresVolume, redisVolume],
  });
});
