param([switch]$JsonOnly)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_054C*' })
$items = @($devices | ForEach-Object {
    $dev = $_
    $props = @{}
    Get-PnpDeviceProperty -InstanceId $dev.InstanceId -ErrorAction SilentlyContinue | ForEach-Object { $props[$_.KeyName] = $_.Data }
    [ordered]@{
        instance_id = $dev.InstanceId
        friendly_name = $dev.FriendlyName
        description = $props['DEVPKEY_Device_BusReportedDeviceDesc']
        status = $dev.Status
        class = $dev.Class
        hardware_ids = $props['DEVPKEY_Device_HardwareIds']
        driver_inf = $props['DEVPKEY_Device_DriverInfPath']
        driver_provider = $props['DEVPKEY_Device_DriverProvider']
        driver_version = $props['DEVPKEY_Device_DriverVersion']
        parent = $props['DEVPKEY_Device_Parent']
    }
})
$result = [ordered]@{
    captured_at = [DateTime]::UtcNow.ToString('o')
    method = 'Windows PnP registry properties only; no application camera commands'
    sony_devices = $items
    camera_setting_write_performed = $false
}
$json = $result | ConvertTo-Json -Depth 8
if (-not $JsonOnly) {
    $reportDir = Join-Path $PSScriptRoot 'reports'
    $null = New-Item -ItemType Directory -Force -Path $reportDir
    $report = Join-Path $reportDir ('inventory-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') + '.json')
    [IO.File]::WriteAllText($report, $json, [Text.UTF8Encoding]::new($false))
    Write-Host "Saved: $report"
}
$json
