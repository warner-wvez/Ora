# Security policy

## Reporting a vulnerability

Email warner@wvez.org with the subject line `Ora security`. Include the file or
URL, what you observed, and the steps to reproduce it. You will get a reply
within five business days, and a fix or a written reason within thirty.

Please do not open a public issue for a security report.

## What is in scope

- The map itself (`index.html`) and the data files it loads from this repo.
- The state builders under `builders/` and the health sweep under `scripts/`.
- The GitHub Actions workflow that commits health verdicts.

## What is out of scope

- The state and city camera feeds the builders read. Report those to the agency.
- Cameras that are offline, frozen, or serving a placeholder. That is data, not a
  vulnerability; the six-hour sweep already records it.

## The two keys you will find in the code

Both are public by design. Neither grants access to anything private.

- The MapTiler key in `index.html` is a browser key. A static site cannot hide
  one, so it is locked to the origins `warner-wvez.github.io` and `localhost`
  in the MapTiler dashboard and can be replaced there at any time.
- The `ApiKey` header in the Tennessee builder is the value smartway.tn.gov
  ships to every visitor's browser. It is quoted, not leaked.

Every other key (Ohio, Washington, Roboflow) is read from the environment and
listed in `.env.example`. If you find a private key anywhere in the tree or the
history, report it the same way; it will be revoked, not just deleted.
