# Security policy

## Supported versions

The latest release for each Blender series the manifest supports. Older series are
handled by their own branches [upstream](https://github.com/teamneoneko/Cats-Blender-Plugin-Unofficial-).

| Blender | Supported |
| --- | --- |
| 5.2 | yes |
| 5.1 | yes |
| 5.0 | yes |
| 4.x and earlier | upstream |

## Reporting a vulnerability

Use [private vulnerability reporting](https://github.com/Zaphkiel-Ivanovna/cats-blender-plugin-unofficial/security/advisories/new)
rather than a public issue.

Worth reporting even though this is a Blender add-on:

- Anything that reaches the network. Cats downloads translations and checks for updates,
  so certificate handling, redirect handling and what it does with a downloaded archive
  all matter.
- Anything that writes outside its own directories, including paths built from a remote
  filename.
- Anything that executes content from a downloaded file.

Expect a first reply within a week. There is no bounty.
