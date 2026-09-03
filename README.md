# Electrode QC

EDF 채널별 Welch PSD figure를 생성하여 전극 신호 품질을 확인하는 도구입니다.

## 구성

- `figure_generator.py`: GUI 입력 및 전체 분석 실행
- `edf_preprocessor.py`: EDF 로딩, sampling frequency와 header 읽기
- `psd_math.py`: 60 Hz 정수배 notch filter와 Welch PSD 계산
- `setup_venv.py`: Python 가상환경과 필요 패키지 설치

## 설치

PowerShell에서 다음을 실행합니다.

```powershell
cd "C:\Users\com\electrode_QC"
python .\setup_venv.py
```

## 실행

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
- 60, 120, 180, 240 Hz에 notch filter를 적용합니다.
- `EKG`부터 `Pleth`까지의 header는 figure 생성에서 제외합니다.
- PSD는 `10*log10(PSD)`로 표시하며 단위는 `dB re 1 uV^2/Hz`입니다.

## Figure 색상

- Channel 전체 Welch PSD의 P5 미만: black
- P5-P95: PSD 값에 따른 선형 spectrum color scale
- P95 초과: white
- 60, 120, 180, 240 Hz: 회색 세로 dashed line

## 결과

선택한 저장 directory 아래 averaging 방식에 맞는 폴더가 자동 생성됩니다.

```text
<output directory>\mean\*.png
<output directory>\median\*.png
```

진행 상황은 terminal의 `Generating ... PSD figure n/216` 메시지로 확인할 수 있습니다.
