param([Parameter(Mandatory=$true)][string]$Evidence, [string]$RepresentativesRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Hash-File([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Read-Json([string]$Name) { Get-Content -LiteralPath (Join-Path $Evidence $Name) -Raw -Encoding UTF8 | ConvertFrom-Json }
$manifest = Read-Json 'manifest.json'
$summary = Read-Json 'summary.json'
$audit = Read-Json 'audit-final.json'
$videos = Read-Json 'video-verification.json'
$manifestSha = Hash-File (Join-Path $Evidence 'manifest.json')
Assert-True ($manifestSha -eq '1757e01b98747133052fe06f97f44c485e043277fb276e0c9df2ab8b6621b3b3') 'Frozen manifest SHA differs'
Assert-True ($summary.manifest_sha256 -eq $manifestSha -and $audit.manifest_sha -eq $manifestSha -and $videos.manifest_sha -eq $manifestSha) 'Evidence manifest identities differ'
Assert-True ($videos.source_sha -eq (Hash-File (Join-Path $Evidence 'verify_videos.py')) -and $audit.audit_source_sha -eq (Hash-File (Join-Path $Evidence 'audit_batch.py'))) 'Verification source identities differ'
Assert-True ($manifest.trials.Count -eq 360 -and $audit.checked -eq 360 -and $audit.failures.Count -eq 0) 'Audit incomplete/failed'
Assert-True ($videos.checked_videos -eq 360 -and $videos.failures.Count -eq 0 -and $videos.videos.Count -eq 360) 'Video checks incomplete/failed'
$expectedIds = @($manifest.trials.id | Sort-Object)
$videoIds = @($videos.videos.id | Sort-Object)
Assert-True ((@($videoIds | Select-Object -Unique)).Count -eq 360 -and ($expectedIds -join ',') -eq ($videoIds -join ',')) 'Video ID set mismatch'
$rows = @{}
foreach ($row in $videos.videos) { $rows[$row.id] = $row }
$computed = @{}
foreach ($name in @('A','B','C','D','NGR','NWS','NGF')) {
    $computed[$name] = @{success=0;physics_failure=0;planning_refused=0;infrastructure_error=0;not_started=0}
}
foreach ($row in $videos.videos) {
    $decodeLog = Join-Path $Evidence ('logs/' + [System.IO.Path]::GetFileName($row.decode_log))
    Assert-True ($row.full_decode_rc -eq 0 -and (Hash-File $decodeLog) -eq $row.log_sha) ('Transferred video decode proof mismatch: ' + $row.id)
}
foreach ($trial in $manifest.trials) {
    $path = Join-Path $Evidence ('out/' + $trial.id + '/result.json')
    $result = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ((Hash-File $path) -eq $rows[$trial.id].source_result_sha) ('Transferred result SHA mismatch: ' + $trial.id)
    Assert-True ($result.runtime_stamp.mujoco_version -eq '3.2.7' -and $result.runtime_stamp.dt -eq 0.001) ('Runtime mismatch: ' + $trial.id)
    if ($result.success) { $outcome = 'success' }
    elseif ($result.classification -eq 'planning_refused') { $outcome = 'planning_refused' }
    elseif ($result.grasp_path_executed) { $outcome = 'physics_failure' }
    else { throw ('Unexpected terminal result: ' + $trial.id) }
    $computed[$trial.group][$outcome]++
    $meta = Get-Content -LiteralPath (Join-Path $Evidence ('out/' + $trial.id + '/replay/replay.json')) -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($meta.id -eq $trial.id -and $meta.video_sha -eq $rows[$trial.id].video_sha -and $meta.source_result_sha -eq $rows[$trial.id].source_result_sha -and $meta.source_trajectory_sha -eq $rows[$trial.id].source_trajectory_sha) ('Replay identity mismatch: ' + $trial.id)
}
if (-not $RepresentativesRoot) {
    $RepresentativesRoot = Join-Path $Evidence 'representatives'
    if (-not (Test-Path -LiteralPath $RepresentativesRoot -PathType Container)) {
        $RepresentativesRoot = Join-Path (Split-Path $Evidence -Parent) 'representatives'
    }
}
$repsRoot = $RepresentativesRoot
$representatives = @()
$groups = @()
foreach ($groupName in @('A','B','C','D','NGR','NWS','NGF')) {
    $group = $summary.groups.$groupName
    Assert-True ($group.counts.not_started -eq 0 -and $group.counts.infrastructure_error -eq 0 -and $group.valid_video_count -eq $group.planned_denominator) ('Incomplete group: ' + $groupName)
    foreach ($outcome in $computed[$groupName].Keys) {
        Assert-True ($group.counts.$outcome -eq $computed[$groupName][$outcome]) ('Summary count differs from original results: ' + $groupName + '/' + $outcome)
    }
    foreach ($kind in @('success','physics_failure')) {
        $trialId = $group.examples_lowest_id.$kind
        if ($null -eq $trialId) { continue }
        $videoPath = Join-Path $repsRoot ($trialId + '/grasp.mp4')
        Assert-True ((Hash-File $videoPath) -eq $rows[$trialId].video_sha) ('Local representative SHA mismatch/missing: ' + $trialId)
        $representatives += [ordered]@{id=$trialId;kind=$kind;group=$groupName;local_path=$videoPath;sha=$rows[$trialId].video_sha;duration_s=$rows[$trialId].measured_container_duration_s}
    }
    $groups += [ordered]@{group=$groupName;planned=$group.planned_denominator;counts=$group.counts;success_rate=$group.success_per_planned;valid_videos=$group.valid_video_count}
}
$report = Get-Content -LiteralPath (Join-Path $Evidence 'REPORT.md') -Raw -Encoding UTF8
foreach ($heading in @('一、结论','二、操作步骤','三、实测证据','四、失败项与原因','五、下一步建议','六、复现方法')) {
    Assert-True ($report.Contains('## ' + $heading)) ('Required report heading missing: ' + $heading)
}
[ordered]@{scope='Local transferred result/decode-proof/metadata and representative identity verification; full trajectories remain on server and are not rehashed locally; no simulation/re-render';manifest_sha=$manifestSha;report_sha=(Hash-File (Join-Path $Evidence 'REPORT.md'));checked_result_files=360;server_independently_verified_videos=360;groups=$groups;representatives=$representatives} | ConvertTo-Json -Depth 12
