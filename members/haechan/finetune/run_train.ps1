# 학습 시작 (백그라운드). Moonlight/원격 연결이 끊겨도 로그인 상태만 유지되면 계속 돈다.
# 사용: .\run_train.ps1 -DataDir "C:\...\finetune_merged" [-Name qwen3-8b-v1] [-Epochs 3]
# 진행 확인: Get-Content .\runs\<Name>\train.log -Tail 20 -Wait
param(
    [Parameter(Mandatory = $true)][string]$DataDir,
    [string]$Name = "qwen3-8b-v1",
    [double]$Epochs = 3
)
Set-Location $PSScriptRoot
$vpy = (Resolve-Path ".\ft-env\Scripts\python.exe").Path
$train = (Resolve-Path (Join-Path $DataDir "train.jsonl")).Path
$val = (Resolve-Path (Join-Path $DataDir "val.jsonl")).Path
$out = Join-Path $PSScriptRoot "runs\$Name"
New-Item -ItemType Directory -Force $out | Out-Null

# VRAM 에 맞춰 배치 결정 (실효 배치는 항상 16): 24GB 이상(4090)=4x4, 그 아래(4080 Super 16GB)=2x8
$vram = [double](& $vpy -c "import torch;print(torch.cuda.get_device_properties(0).total_memory/2**30)")
if ($vram -ge 22) { $batch = 4; $accum = 4 } else { $batch = 2; $accum = 8 }
Write-Host "VRAM $([math]::Round($vram,1))GB -> batch $batch x accum $accum"

$log = Join-Path $out "train.log"
$cmd = "& '$vpy' -X utf8 -u train_qlora.py --train '$train' --val '$val' --out '$out' --epochs $Epochs --batch $batch --accum $accum *>&1 | Tee-Object -FilePath '$log'"
Start-Process powershell -WindowStyle Minimized -ArgumentList "-NoProfile", "-Command", $cmd
Write-Host "학습 시작. 로그: $log"
Write-Host "확인: Get-Content '$log' -Tail 20 -Wait"
Write-Host "주의: PC 가 절전에 들어가지 않게 하고, Windows 에서 로그아웃하지 말 것."
