# qubelets

My Qubes script framework. The scripts rely on configured values. The code bridges the gaps between domains.

## The global configuration file

This is the source of truth for how Qubelets behaves.


```toml
[app.terminal.default]
cmd = "alacritty" 
exec = "alacritty --command %s" 

[app.terminal.graphics]
cmd = "kitty"
exec = "kitty --command %s"

```

### Key descriptions

A description of each key.

#### `app`
Mappings of applications to their function.

| Key                                    | Description                                                 |
| -------------------------------------- | ----------------------------------------------------------- |
| `app`                          | App configurations.                                         |
| `app.<type>`                   | An arbitrary category of app.                               |
| `app.<type>.<profile>`         | An arbitrary name that describes its use case.              |
| `app.<type>.<profile>.cmd`     | The command to run.                                         |
| `app.<type>.<profile>.exec`    | Execution template; any `%s` gets interpolated with args.   |


