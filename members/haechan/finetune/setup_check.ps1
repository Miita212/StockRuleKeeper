# 파인튜닝 환경 확인·설치 (Windows PowerShell). 4080 Super / 4090 어느 쪽이든 같은 스크립트를 쓴다.
# 사용: PowerShell 을 열고 이 폴더에서
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\setup_check.ps1 -DataDir "C:\...\finetune_merged"      # train.jsonl, val.jsonl 이 있는 폴더
# 결과는 화면과 setup_log.txt 에 같이 남는다. 끝나면 setup_log.txt 내용을 알려 주면 된다.
param(
    [string]$DataDir = ""
)
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
Start-Transcript -Path (Join-Path $PSScriptRoot "setup_log.txt") -Force | Out-Null

function Step($t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }
$problems = @()

Step "1. GPU"
$gpu = $null
try { $gpu = nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1 } catch {}
if ($LASTEXITCODE -ne 0 -or -not $gpu) { $problems += "nvidia-smi 가 안 된다 (NVIDIA 드라이버 확인)"; Write-Host "GPU 못 찾음" -ForegroundColor Red }
else { Write-Host $gpu }

Step "2. 파이썬 / git / 디스크"
$py = (python --version) 2>&1
Write-Host "python: $py"
if ($py -notmatch "3\.(10|11|12)") { $problems += "파이썬 3.10~3.12 권장 (지금: $py)" }
Write-Host ("git: " + ((git --version) 2>&1))
$drive = (Get-Item $PSScriptRoot).PSDrive
$freeGB = [math]::Round($drive.Free / 1GB, 1)
Write-Host "디스크 여유 ($($drive.Name):): $freeGB GB (모델 17GB + 결과 2GB 필요)"
if ($freeGB -lt 25) { $problems += "디스크 여유가 25GB 미만" }

Step "3. 가상환경 + 라이브러리 (처음이면 10~20분)"
if (-not (Test-Path ".\ft-env\Scripts\python.exe")) { python -m venv ft-env }
$vpy = (Resolve-Path ".\ft-env\Scripts\python.exe").Path
& $vpy -m pip install --upgrade pip -q
$hasTorch = & $vpy -c "import torch;print(torch.cuda.is_available())" 2>$null
if ($hasTorch -ne "True") {
    & $vpy -m pip install torch --index-url https://download.pytorch.org/whl/cu126
}
& $vpy -m pip install -r requirements.txt -q

Step "4. 설치 확인"
& $vpy -c "import torch,transformers,peft,bitsandbytes,accelerate as a;print('torch',torch.__version__,'cuda',torch.cuda.is_available());print('transformers',transformers.__version__,'peft',peft.__version__,'bitsandbytes',bitsandbytes.__version__)"
if ($LASTEXITCODE -ne 0) { $problems += "라이브러리 import 실패 (위 에러 확인)" }
$cuda = & $vpy -c "import torch;print(torch.cuda.is_available())" 2>$null
if ($cuda -ne "True") { $problems += "torch 가 GPU 를 못 쓴다 (CPU 용 torch 가 깔렸거나 드라이버 문제)" }
else {
    $vram = & $vpy -c "import torch;print(round(torch.cuda.get_device_properties(0).total_memory/2**30,1))"
    Write-Host "VRAM: $vram GB"
}

Step "5. 학습 데이터 찾기"
$train = $null; $val = $null
$cands = @($DataDir, (Join-Path $PSScriptRoot "..\..\byungjun\finetune_merged"), (Join-Path $PSScriptRoot "data"), $PSScriptRoot) | Where-Object { $_ }
foreach ($c in $cands) {
    if ((Test-Path (Join-Path $c "train.jsonl")) -and (Test-Path (Join-Path $c "val.jsonl"))) { $train = (Resolve-Path (Join-Path $c "train.jsonl")).Path; $val = (Resolve-Path (Join-Path $c "val.jsonl")).Path; break }
}
if (-not $train) { $problems += "train.jsonl / val.jsonl 을 못 찾았다. -DataDir 로 폴더를 알려 줘야 한다"; Write-Host "못 찾음" -ForegroundColor Red }
else {
    Write-Host "train: $train ($((Get-Content $train | Measure-Object -Line).Lines)줄)"
    Write-Host "val:   $val ($((Get-Content $val | Measure-Object -Line).Lines)줄)  (기대값: 2090 / 111)"
}

Step "6. 토큰화 시험 (dry-run, 토크나이저만 내려받음)"
if ($train) {
    & $vpy -X utf8 train_qlora.py --dry-run --train $train --val $val
    if ($LASTEXITCODE -ne 0) { $problems += "dry-run 실패 (위 에러 확인)" }
}

Step "결과"
if ($problems.Count -eq 0) { Write-Host "문제 없음. 다음은 .\run_train.ps1 -DataDir <폴더>" -ForegroundColor Green }
else { Write-Host "확인할 것:" -ForegroundColor Yellow; $problems | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow } }
Stop-Transcript | Out-Null
