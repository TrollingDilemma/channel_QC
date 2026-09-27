# Electrode QC

EDF 채널별 Welch PSD figure를 생성하여 전극 신호 품질을 확인하는 도구입니다.

## 구성

- `figure_generator.py`: GUI 입력 및 전체 분석 실행
- `edf_preprocessor.py`: EDF 로딩, sampling frequency와 header 읽기
- `psd_math.py`: 60 Hz 정수배 notch filter와 Welch PSD 계산
- `setup_venv.py`: Python 가상환경과 필요 패키지 설치

## 설치

프로젝트를 다운로드하거나 압축 해제한 뒤 PowerShell을 엽니다. 아래의 `<프로젝트 폴더 경로>`를 자신의 PC에서 `setup_venv.py`가 들어 있는 폴더의 실제 경로로 바꾸어 실행합니다. 경로에 공백이 있을 수 있으므로 큰따옴표는 유지합니다.

```powershell
cd "<프로젝트 폴더 경로>"
python .\setup_venv.py
```

## 실행

설치할 때 이동한 프로젝트 폴더에서 다음을 실행합니다.

```powershell
.\.venv\Scripts\python.exe .\figure_generator.py
```

표시되는 창에 다음 항목을 입력합니다.

1. EDF 파일이 있는 directory
2. `.edf` 확장자를 포함한 파일명
3. Figure를 저장할 directory
4. Welch averaging 방식: `mean` 또는 `median`

## 분석 방식

- `ANALYSIS_ON`부터 `ANALYSIS_OFF`까지의 annotation 구간만 분석합니다.
- 분석 구간이 여러 개이면 각 구간의 Welch segment를 이어서 계산합니다.
- Welch window는 2초, overlap은 50%입니다.
- EDF를 읽은 MNE 객체의 sampling frequency를 사용합니다.
- PSD 계산 범위는 1–512 Hz입니다. Sampling frequency가 1,024 Hz 미만이면 실제 계산 가능한 범위는 Nyquist frequency(sampling frequency의 절반)까지입니다.
- 60, 120, 180, 240, 300, 360, 420, 480 Hz 중 Nyquist frequency보다 낮은 주파수에 notch filter를 적용합니다.
- `EKG`부터 `Pleth`까지의 header는 figure 생성에서 제외합니다.
- PSD는 `10*log10(PSD)`로 표시하며 단위는 `dB re 1 uV^2/Hz`입니다.

## Figure 색상

- x축은 1–512 Hz로 표시합니다.
- 실제 notch filter가 적용된 각 주파수의 ±5 Hz 구간(경계 포함)에서는 점을 표시하지 않습니다. 회색 PSD 연결선은 유지하며, PSD 계산값 자체를 제외하지는 않습니다.
- Channel 전체 Welch PSD의 P5 미만: black
- P5-P95: PSD 값에 따른 선형 spectrum color scale
- P95 초과: white
- 실제 notch filter가 적용된 주파수: 회색 세로 dashed line

## 결과

선택한 저장 directory 아래 averaging 방식에 맞는 폴더가 자동 생성됩니다.

```text
<output directory>\mean\*.png
<output directory>\median\*.png
```

진행 상황은 terminal의 `Generating ... PSD figure n/전체 채널 수` 메시지로 확인할 수 있습니다.
