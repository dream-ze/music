# Refresh installed tools even when the parent app started before installation.
$installedPaths = @(
    [Environment]::GetEnvironmentVariable('Path', 'Machine'),
    [Environment]::GetEnvironmentVariable('Path', 'User')
)
$env:Path = (@($env:Path) + $installedPaths) -join ';'
