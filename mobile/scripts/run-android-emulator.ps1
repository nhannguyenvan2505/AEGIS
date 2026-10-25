param(
    [string]$AvdName = 'Pixel_7',
    [string]$DeviceId = 'emulator-5554'
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ([IO.Path]::GetPathRoot($projectRoot) -ne 'D:\') {
    throw 'Run this project from drive D so build files stay off drive C.'
}

$buildState = Join-Path $projectRoot '.expo'
$env:GRADLE_USER_HOME = Join-Path $buildState 'gradle-home'
$env:TEMP = Join-Path $buildState 'build-tmp'
$env:TMP = $env:TEMP
$env:npm_config_cache = Join-Path $buildState 'npm-cache'
$env:__UNSAFE_EXPO_HOME_DIRECTORY = Join-Path $buildState 'expo-build-home'
$env:AEGIS_LOW_MEMORY_BUILD = '1'
$env:NODE_ENV = 'production'
$env:CI = '1'
$env:NODE_OPTIONS = '--max-old-space-size=1024'
$env:JAVA_TOOL_OPTIONS = "-Xms32m -Xmx384m -XX:MaxMetaspaceSize=256m -XX:+UseSerialGC -Djava.io.tmpdir=$env:TEMP"
$env:CMAKE_BUILD_PARALLEL_LEVEL = '1'

foreach ($directory in @($env:GRADLE_USER_HOME, $env:TEMP, $env:npm_config_cache, $env:__UNSAFE_EXPO_HOME_DIRECTORY)) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

if (Test-Path -LiteralPath 'C:\Program Files\Java\jdk-17\bin\java.exe') {
    $env:JAVA_HOME = 'C:\Program Files\Java\jdk-17'
}
if (!$env:ANDROID_HOME -or !(Test-Path -LiteralPath $env:ANDROID_HOME)) {
    if (Test-Path -LiteralPath 'E:\Android_SDK') { $env:ANDROID_HOME = 'E:\Android_SDK' }
    else { throw 'ANDROID_HOME must point to an installed Android SDK.' }
}
$adb = Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
$emulator = Join-Path $env:ANDROID_HOME 'emulator\emulator.exe'

Push-Location $projectRoot
try {
    & npm.cmd run styles
    if ($LASTEXITCODE -ne 0) { throw 'Style generation failed.' }

    if (!(Test-Path -LiteralPath 'android\gradlew.bat')) {
        $packagePath = Join-Path $projectRoot 'package.json'
        $beforePackage = Get-Content -LiteralPath $packagePath -Raw | ConvertFrom-Json
        & npx.cmd expo prebuild --platform android --no-install
        if ($LASTEXITCODE -ne 0) { throw 'Expo Android prebuild failed.' }

        # Preserve the existing Expo Go commands that prebuild replaces.
        $packageText = [IO.File]::ReadAllText($packagePath)
        foreach ($platform in @('android', 'ios')) {
            $original = $beforePackage.scripts.$platform
            if ($original) {
                $generatedEntry = '"' + $platform + '": "expo run:' + $platform + '"'
                $originalEntry = '"' + $platform + '": ' + (ConvertTo-Json -InputObject $original -Compress)
                $packageText = $packageText.Replace($generatedEntry, $originalEntry)
            }
        }
        [IO.File]::WriteAllText($packagePath, $packageText, (New-Object Text.UTF8Encoding($false)))
    }

    Push-Location (Join-Path $projectRoot 'android')
    try {
        $gradleArgs = @(
            ':app:assembleRelease',
            '-PreactNativeArchitectures=x86_64',
            '-Pkotlin.compiler.execution.strategy=in-process',
            '-Dorg.gradle.parallel=false',
            "-Dorg.gradle.jvmargs=-Xmx1024m -Xms128m -XX:MaxMetaspaceSize=512m -XX:+UseSerialGC -Djava.io.tmpdir=$env:TEMP",
            '--max-workers', '1', '--console=plain'
        )
        Write-Output 'Building for the x86_64 emulator. Build cache and temporary files are on D.'
        & .\gradlew.bat @gradleArgs
        $buildExitCode = $LASTEXITCODE
        & .\gradlew.bat --stop --console=plain
        if ($buildExitCode -ne 0) { throw 'Android emulator build failed.' }
    } finally {
        Pop-Location
    }

    # Free the build daemon memory before starting the interactive emulator.
    $connectedDevices = & $adb devices
    if (!($connectedDevices -match "^$([regex]::Escape($DeviceId))\s+device$")) {
        if ($connectedDevices -match "^$([regex]::Escape($DeviceId))\s+offline$") {
            Write-Output 'Waiting for the existing emulator to finish starting.'
        } else {
            Write-Output "Starting the interactive emulator: $AvdName"
            Start-Process -FilePath $emulator -ArgumentList @('-avd', $AvdName, '-no-snapshot-save') -WindowStyle Normal | Out-Null
        }
    }
    $bootDeadline = (Get-Date).AddMinutes(5)
    do {
        Start-Sleep -Seconds 2
        try { $bootComplete = & $adb -s $DeviceId shell getprop sys.boot_completed 2>$null }
        catch { $bootComplete = '' }
        if ((Get-Date) -gt $bootDeadline) { throw "Emulator $DeviceId did not finish booting." }
    } while (($bootComplete -join '').Trim() -ne '1')

    $apkPath = Join-Path $projectRoot 'android\app\build\outputs\apk\release\app-release.apk'
    & $adb -s $DeviceId install -r $apkPath
    if ($LASTEXITCODE -ne 0) { throw 'APK installation failed. Existing app data was preserved.' }
    & $adb -s $DeviceId shell am start -W -n 'com.aegis.mobile/.MainActivity'
    if ($LASTEXITCODE -ne 0) { throw 'Could not launch Farmer App.' }
    Write-Output 'Farmer App is installed and running on the emulator.'
} finally {
    Pop-Location
}
