# CDN publishing on GitLab

The root `.gitlab-ci.yml` includes `.gitlab/ci/publish.yml`, replacing the
production GitHub Actions publish workflow. Existing GitLab lint jobs are
unchanged. Pushes and merge requests do not deploy.

## One-time setup

1. Protect the project's default branch under **Settings > Repository > Branch
   rules**. Publishing is allowed only from the protected default branch of
  [projectwayfarer/wayfarer14](https://gitlab.com/projectwayfarer/wayfarer14).
2. Under **Settings > CI/CD > Variables**, add `PUBLISH_TOKEN` as a **masked,
   protected** variable of type **Variable**, not File. Use the token issued by
   the Robust.Cdn server. GitHub secrets are not transferred to GitLab.
   If using an environment scope, select `production` (or `*`).
3. Ensure a Linux x86-64 runner with a Docker or Kubernetes executor is available
   to this project and allowed to run protected-branch jobs. It must support the
   .NET SDK container image, package installation as root, and outbound access to
   GitHub (the engine submodule), NuGet, Debian package mirrors, and the CDN.
   Allow sufficient memory, disk space, and job timeout for four server builds
   plus the client build. Shell executors do not provision the configured image.
4. Review `ROBUST_CDN_URL` and `FORK_ID` in `Tools/publish_multi_request.py`.
   They currently target `http://dev.wayfarer14.com:8080/` and `wayfarer14`.
   **The current HTTP URL transmits the bearer token and packages unencrypted.**
   Configure HTTPS on the CDN/reverse proxy and update that URL before publishing
   over an untrusted network. No CDN endpoint or credentials are changed by this
   migration.

## Run a release

In **Build > Pipelines > New pipeline**, select the protected default branch and
run the pipeline. The `publish_cdn` job starts automatically for this explicitly
requested pipeline. It restores dependencies, builds packaging, packages the
Windows x64, Linux x64, macOS x64, and Linux ARM64 servers and the client, then
uploads the files directly to Robust.Cdn. There is no separate GitLab artifact
upload, avoiding artifact size limits for these packages.

The full GitLab commit SHA becomes the CDN version through the uploader's legacy
`GITHUB_SHA` environment variable. Engine tags and full submodule history are
fetched so the uploader can resolve the engine release. Neither a GitHub token
nor a `GITHUB_REPOSITORY` variable is needed for CDN publishing.

To restore the old daily schedule, create a **Build > Pipeline schedules** entry
with cron `0 10 * * *`, timezone **UTC**, and the protected default branch as its
target. GitLab schedules live in the project settings, not in pipeline YAML.
The schedule owner must have permission to run pipelines on that branch and
deploy to `production` if the environment is protected.

`resource_group: publish` serializes deployments, and publishing is not
interruptible. Do not manually cancel a job during upload: the CDN uses a
start/files/finish sequence. Avoid queuing obsolete releases; if several releases
are queued, cancel unwanted **pending** jobs before they start. 

## Discord changelog publishing

The included `.gitlab/ci/publish-changelog.yml` runs `publish_changelog` after
`publish_cdn` succeeds, only for the same protected production release pipelines.
Failures are non-blocking. Pushes, merge requests, and fork pipelines cannot send
notifications. Jobs are serialized; avoid running obsolete releases out of order
and cancel obsolete pending notification jobs along with their releases.

Add these **masked, protected** CI/CD variables (type **Variable**, environment
scope `production` or `*`):

- `CHANGELOG_DISCORD_WEBHOOK`: the Discord webhook URL previously stored in
  GitHub secrets. The job maps it to the script's `DISCORD_WEBHOOK_URL`.
- `CHANGELOG_GITLAB_TOKEN`: a project access token with Reporter role and
  `read_api` scope, or an equivalently authorized personal access token. It reads
  project job history and historical repository files. `CI_JOB_TOKEN` cannot
  list project jobs; no GitHub token or checkout PAT is needed.

The script compares `Resources/Changelog/Wayfarer.yml` with the version from the
previous successful `publish_changelog` job on the same ref, paginating history
and skipping the current/newer jobs. With no history, the first successful run
establishes a baseline **without sending old entries**. To send changes since a
known release on the first run, temporarily set `CHANGELOG_BASE_SHA` to that
commit SHA and remove it immediately afterward; leaving it set repeats entries.
Missing historical files and API failures fail the notification job rather than
replaying the entire changelog. Configure the webhook before the first run: a
missing webhook intentionally skips sending and still establishes a baseline.

Discord sends are not transactional: retrying after a partial send may repeat
messages. No live Discord messages are sent by local validation.

## Changelogs and remaining GitHub workflows

- RSS publishing remains optional and non-blocking. The RSS script still points
  at Wizard's Den's SSH host and feed metadata. Configure those settings in
  `Tools/actions_changelog_rss.py` for your infrastructure before adding
  `CHANGELOG_RSS_KEY` as a protected variable of type **Variable**. The script
  expects the key contents, not a GitLab File variable's path.
- Legacy GitHub callers can still use the Discord script's GitHub API path.
- Other GitHub workflows, including staging/testing publication, are not migrated
  here. Disable their GitHub execution if GitHub publishing should stop entirely.

Validate the merged configuration in GitLab's **Pipeline editor > Validate**
before the first release. Local validation does not verify runner access, secret
availability, package builds, or CDN connectivity.