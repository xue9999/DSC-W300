param([Parameter(Mandatory)][string]$InstanceId, [Parameter(Mandatory)][string]$OutputDirectory)
# Read-only Windows inventory. No device handles, vendor commands, or configuration changes.
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Output directory already exists; preserve captures.' }
$target = Get-PnpDevice -PresentOnly -InstanceId $InstanceId
$identity = @(Get-PnpDeviceProperty -InstanceId $InstanceId)
if ($InstanceId -notlike 'USB\VID_054C&PID_0341\*' -or ($identity | Where-Object KeyName -eq 'DEVPKEY_Device_BusReportedDeviceDesc').Data -ne 'DSC-W300') { throw 'Current device is not the requested DSC-W300.' }
$null = New-Item -ItemType Directory -Path $OutputDirectory
$results = [ordered]@{ captured_at_utc=[DateTime]::UtcNow.ToString('o'); selected_instance_id=$InstanceId; method='Windows OS inventory; no device configuration or vendor commands'; camera_write_commands_sent=$false; sections=[ordered]@{} }
function Capture($Name, [scriptblock]$Read) {
    try { $results.sections[$Name] = @{ok=$true; data=@(& $Read)} }
    catch { $results.sections[$Name] = @{ok=$false; error=$_.Exception.Message} }
}
$nodes = [Collections.Generic.List[string]]::new()
$nodes.Add($InstanceId)
$serial = $InstanceId.Split('\')[-1]
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like "USBSTOR\*\$serial*" } | ForEach-Object { $nodes.Add($_.InstanceId) }
$ancestor = $InstanceId
for ($i=0; $i -lt 8; $i++) {
    $parent = (Get-PnpDeviceProperty -InstanceId $ancestor -KeyName DEVPKEY_Device_Parent -ErrorAction SilentlyContinue).Data
    if (-not $parent -or $nodes.Contains($parent)) { break }
    $nodes.Add($parent); $ancestor=$parent
}
Capture 'device_tree' { foreach ($id in $nodes) { @{ instance_id=$id; device=Get-PnpDevice -InstanceId $id | Select-Object * -ExcludeProperty CimClass,CimInstanceProperties,CimSystemProperties; properties=@(Get-PnpDeviceProperty -InstanceId $id | Select-Object KeyName,Type,Data) } } }
Capture 'signed_drivers' { Get-CimInstance Win32_PnPSignedDriver | Where-Object { $nodes -contains $_.DeviceID } | Select-Object * -ExcludeProperty CimClass,CimInstanceProperties,CimSystemProperties }
Capture 'camera_disk_cim' { Get-CimInstance Win32_DiskDrive | Where-Object { $_.PNPDeviceID -like "*$serial*" } | Select-Object * -ExcludeProperty CimClass,CimInstanceProperties,CimSystemProperties }
Capture 'camera_storage_disks' { Get-Disk | Where-Object { $_.SerialNumber -like "*$serial*" -or $_.FriendlyName -like '*Sony*' } | Select-Object * -ExcludeProperty CimClass,CimInstanceProperties,CimSystemProperties }
Capture 'logical_disks' { Get-CimInstance Win32_LogicalDisk | Select-Object DeviceID,DriveType,FileSystem,VolumeName,VolumeSerialNumber,Size,FreeSpace,Status }
Capture 'volumes' { Get-Volume | Select-Object DriveLetter,FileSystemLabel,FileSystem,Size,SizeRemaining,Path,UniqueId,HealthStatus,OperationalStatus }
Capture 'filesystem_drives' { Get-PSDrive -PSProvider FileSystem | Select-Object Name,Root,Description,DisplayRoot }
Capture 'usb_registry' { Get-ItemProperty -LiteralPath "Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Enum\$InstanceId" | Select-Object * -ExcludeProperty PSPath,PSParentPath,PSChildName,PSDrive,PSProvider }
Capture 'host' { Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture; @{ powershell=$PSVersionTable.PSVersion.ToString(); elevated=([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) } }
Capture 'driver_services' { Get-CimInstance Win32_SystemDriver | Where-Object Name -in @('USBSTOR','disk','USBHUB3','CSDeviceControl') | Select-Object Name,DisplayName,State,StartMode,PathName,ServiceType }
foreach ($id in $nodes | Select-Object -First 2) {
    $name = if ($id -eq $InstanceId) { 'usb' } else { 'disk' }
    Capture "pnputil_$name" { $out = & pnputil.exe /enum-devices /instanceid $id /properties /drivers /interfaces /relations /stack /services 2>&1; @{exit_code=$LASTEXITCODE; output=($out -join "`n")} }
}
Capture 'identity_at_end' { Get-PnpDevice -PresentOnly -InstanceId $InstanceId | Select-Object InstanceId,Status,Class,FriendlyName }
$results.completed_at_utc=[DateTime]::UtcNow.ToString('o')
$results | ConvertTo-Json -Depth 25 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'windows-inventory.json') -Encoding utf8
Write-Output $OutputDirectory
