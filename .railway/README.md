# Railway configuration

`railway.ts` defines the Railway project for every environment: services, settings,
replicas, domains and variables. `plans/deploy.md` explains the layout and the rules
for changing it.

Run from this folder, with Node 22.6 or later (`nvm use`):

```bash
npm install                                         # the railway SDK, pinned
railway config plan --environment staging           # preview; changes nothing
railway config apply --environment staging          # apply after reading the plan
```

Never pass `--include-variables` to `railway config pull`: it writes secret values
into this file.
