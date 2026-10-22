// Dependencies
const fs = require("fs");
const yaml = require("js-yaml");
const axios = require("axios");

const isGitLab = process.env.GITLAB_CI === "true";

// Use GitHub token if available
if (!isGitLab && process.env.GITHUB_TOKEN) axios.defaults.headers.common["Authorization"] = `Bearer ${process.env.GITHUB_TOKEN}`;

// Check changelog directory.
if (!process.env.CHANGELOG_DIR) {
    console.log("CHANGELOG_DIR not defined, exiting.");
    return process.exit(1);
}

const ChangelogFilePath = `../../../${process.env.CHANGELOG_DIR}`

// Regexes
const HeaderRegex = /^\s*(?::cl:|🆑) *([a-z0-9_\-, ]+)?/img; // :cl: or 🆑 [0] followed by optional author name [1]
const EntryRegex = /^ *[*-]? *(add|remove|tweak|fix): *([^\n\r]+)\r?$/img; // * or - followed by change type [0] and change message [1]
const CommentRegex = /<!--.*?-->/gs; // HTML comments

// Fetch the merged PR/MR as { merged_at, body, author, url, number }
async function getPullRequest() {
    if (!isGitLab) {
        const pr = await axios.get(`https://api.github.com/repos/${process.env.GITHUB_REPOSITORY}/pulls/${process.env.PR_NUMBER}`);
        return {
            merged_at: pr.data.merged_at,
            body: pr.data.body,
            author: pr.data.user.login,
            url: url,
            number: process.env.PR_NUMBER,
        };
    }

    // On GitLab this runs in a push pipeline on the default branch; find the MR that produced the pushed commit.
    const token = process.env.CHANGELOG_GITLAB_TOKEN;
    if (!token) throw new Error("Configure CHANGELOG_GITLAB_TOKEN with api and write_repository access");

    const api = process.env.CI_API_V4_URL.replace(/\/+$/, "");
    const res = await axios.get(
        `${api}/projects/${encodeURIComponent(process.env.CI_PROJECT_ID)}/repository/commits/${process.env.CI_COMMIT_SHA}/merge_requests`,
        { headers: { "PRIVATE-TOKEN": token } }
    );
    const mr = res.data.find((m) => m.state === "merged" && m.target_branch === process.env.CI_DEFAULT_BRANCH);
    if (!mr) return null;

    return {
        merged_at: mr.merged_at,
        body: mr.description || "",
        author: mr.author.username,
        url: mr.web_url,
        number: mr.iid,
    };
}

// Main function
async function main() {
    // Get PR details
    const pr = await getPullRequest();
    if (!pr) {
        console.log("No merged merge request found for this commit, skipping");
        return;
    }
    const { merged_at, body, author: prAuthor, url, number } = pr;

    // Remove comments from the body
    commentlessBody = (body || "").replace(CommentRegex, '');

    // Get author
    const headerMatch = HeaderRegex.exec(commentlessBody);
    if (!headerMatch) {
        console.log("No changelog entry found, skipping");
        return;
    }

    let author = headerMatch[1];
    if (!author) {
        console.log("No author found, setting it to author of the PR\n");
        author = prAuthor;
    } else {
        author = author.trim()
    }

    // Offset results past the header
    commentlessBody = commentlessBody.slice(HeaderRegex.lastIndex);

    // Get all changes from the body
    const entries = getChanges(commentlessBody);


    // Time is something like 2021-08-29T20:00:00Z
    // Time should be something like 2023-02-18T00:00:00.0000000+00:00
    let time = merged_at;
    if (time)
    {
        // Drop any fractional seconds (GitLab includes them) and normalize the UTC suffix
        time = time.replace(/(\.\d+)?[zZ]$/, ".0000000+00:00");
    }
    else
    {
        console.log("Pull request was not merged, skipping");
        return;
    }


    // Construct changelog yml entry
    const entry = {
        author: author,
        changes: entries,
        id: getHighestCLNumber() + 1,
        time: time,
        url: url,
    };

    // Write changelogs
    writeChangelog(entry);

    console.log(`Changelog updated with changes from PR #${number}`);
}


// Code chunking

// Get all changes from the PR body
function getChanges(body) {
    const matches = [];
    const entries = [];

    for (const match of body.matchAll(EntryRegex)) {
        matches.push([match[1], match[2]]);
    }

    if (!matches)
    {
        console.log("No changes found, skipping");
        return;
    }


    // Check change types and construct changelog entry
    matches.forEach((entry) => {
        let type;

        switch (entry[0].toLowerCase()) {
            case "add":
                type = "Add";
                break;
            case "remove":
                type = "Remove";
                break;
            case "tweak":
                type = "Tweak";
                break;
            case "fix":
                type = "Fix";
                break;
            default:
                break;
        }

        if (type) {
            entries.push({
                type: type,
                message: entry[1],
            });
        }
    });

    return entries;
}

// Get the highest changelog number from the changelogs file
function getHighestCLNumber() {
    // Read changelogs file
    const file = fs.readFileSync(ChangelogFilePath, "utf8");

    // Get list of CL numbers
    const data = yaml.load(file);
    const entries = data && data.Entries ? Array.from(data.Entries) : [];
    const clNumbers = entries.map((entry) => entry.id);

    // Return highest changelog number
    return Math.max(...clNumbers, 0);
}

function writeChangelog(entry) {
    let data = { Entries: [] };

    // Create a new changelogs file if it does not exist
    if (fs.existsSync(ChangelogFilePath)) {
        const file = fs.readFileSync(ChangelogFilePath, "utf8");
        data = yaml.load(file);
    }

    data.Entries.push(entry);

    // Write updated changelogs file
    fs.writeFileSync(
        ChangelogFilePath,
        "Entries:\n" +
            yaml.dump(data.Entries, { indent: 2 }).replace(/^---/, "")
    );
}

// Run main
main();
