"""Write player-facing documentation from the certified audio manifest."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    quality=json.loads((args.source/'quality_summary.json').read_text(encoding='utf-8'))
    assert quality['ready_to_install'],'Finish audio validation before preparing release documentation'
    version=args.version;count=quality['speech_files'];voices=len(quality['cast'])
    base='https://github.com/EugeneMarkeev/bugsnax_ru'
    installer=f'{base}/releases/download/v{version}/Bugsnax-Installer-v{version}.zip'
    sound=f'{base}/releases/download/v{version}/Bugsnax-Sound-Pack-v{version}.zip'
    readme=f'''# Bugsnax — русская озвучка

[![Проверки установщиков]({base}/actions/workflows/tests.yml/badge.svg)]({base}/actions/workflows/tests.yml)

**[Скачать установщик Windows / macOS]({installer})** · [Звуковой пакет отдельно]({sound}) · [Все релизы]({base}/releases)

Неофициальная озвучка Qwen3-TTS: **{count} русских голосовых фрагментов,
{voices} постоянных голосов персонажей**. Переведены сюжетные диалоги, задания,
интервью, дневники и отобранные разговорные фразы без субтитров, включая DLC.
Песни, неречевые звуки, голоса жуконямок и неиспользуемые материалы трейлеров
сохранены в оригинале. [Голоса персонажей](docs/voices.txt).

## Установка

1. [Скачайте установщик]({installer}) и распакуйте ZIP в новую папку.
2. Закройте Bugsnax.
3. Windows: откройте **Install.cmd**. Mac: **Install.command**.
4. Установщик скачает звуковой пакет (около 1,3 ГБ), проверит его и установит
   с резервной копией оригиналов. После обрыва запустите установщик повторно.
5. Запускайте Bugsnax через Steam. Для русского интерфейса и субтитров выберите
   русский язык в свойствах игры в Steam.

Для установки без интернета [скачайте пакет звуков]({sound}) и положите ZIP
рядом с Install.cmd / Install.command или в родительскую папку.
Установщик использует этот архив автоматически.

Установщик ищет игру в библиотеках Steam, в том числе на другом диске.
Если понадобится выбрать путь вручную: Steam → Bugsnax → Управление →
Просмотреть локальные файлы. На Mac можно выбрать Bugsnax.app или папку
Content/Audio/Build/Desktop внутри приложения.

Если Mac не разрешает запуск .command, откройте Terminal, введите `bash `,
перетащите Install.command в окно и нажмите Enter. Установка выполняется
с правами текущего пользователя, без sudo.

## Обновление и удаление

Для обновления распакуйте новый установщик в отдельную папку и запустите его.
Он поддерживает прежние версии нашего пакета и сохраняет оригинальные резервные
копии. В v0.1.0–v0.1.1 была ошибка банков, вызывавшая писк диалогов; новая
сборка содержит исправленные банки и дополнительные русские реплики.
Для этого обновления нужен новый звуковой пакет целиком.

Для удаления запустите **Uninstall.cmd** или **Uninstall.command**.
Восстановятся оригинальные банки из `.bugsnax-russian-voice/backup` в папке
звуков игры. Удаление работает без интернета. Сохранения игры не изменяются.

Проверка целостности или обновление игры в Steam может вернуть оригинальные
голоса. В таком случае установите озвучку повторно. При неизвестных контрольных
суммах установщик остановится: нужен совместимый релиз мода.
Другие моды, заменяющие те же звуковые банки, могут конфликтовать.

Для архива и распакованных звуков понадобится около 3,2 GiB в папке установщика,
а для резервных и временных копий — ещё до 5 GiB на диске игры.

## Проверки и совместимость

Установщики проверены на Windows, Intel macOS и Apple Silicon macOS в CI.
Все упакованные PCM-записи проверены побайтово через FMOD Windows-версии игры.
Дополнительно проверены привязки событий и речь с выхода игрового микшера
в начале игры, финале, DLC и репликах Сладколапа.

**Воспроизведение на настоящем Mac и полное прохождение пока не проверены.**
Совместимость определяется контрольными суммами исходных банков; эталонная
Steam-сборка Windows — 25460845. [Отчёт проверок](docs/AUDIO_VALIDATION_v{version}.json).
[Сообщить об ошибке]({base}/issues/new/choose).

## Для разработчика

Установщики, манифесты и документация находятся в Git. Готовые звуковые банки
публикуются отдельно в GitHub Releases. Исходные резервные копии игры и модели
генерации в репозиторий не включены.

```text
python -m unittest discover -s tests -v
python tools/build_split_release.py --source /path/to/certified/audio --version {version} --sound-version {version}
```
'''
    (ROOT/'README.md').write_text(readme,encoding='utf-8')
    notes=f'''# v{version} — русская озвучка Bugsnax

- {count} голосовых фрагментов и {voices} постоянных голосов, включая отдельный голос Сладколапа.
- Завершён план сюжетных диалогов и добавлены разговорные записи без субтитров, включая DLC.
- Исправлены ошибочные привязки голосов и адаптированы реплики под исходные тайминги.
- Обновление с прежних пакетов, резервные копии, проверка SHA-256 и откат при ошибке.
- Песни, неречевые звуки и голоса существ сохранены в оригинале.
- Побайтовая проверка PCM через FMOD игры, проверка событий и записи микшера.
- Установщики проверены на Windows, Intel macOS и Apple Silicon macOS. Нативное воспроизведение на Mac и полное прохождение пока не проверены.

Скачайте Bugsnax-Installer-v{version}.zip. Он скачает звуковой пакет автоматически.
Для установки без сети положите Bugsnax-Sound-Pack-v{version}.zip рядом с установщиком.
'''
    (ROOT/f'docs/RELEASE_NOTES_v{version}.md').write_text(notes,encoding='utf-8')
    path=ROOT/'CHANGELOG.md';old=path.read_text(encoding='utf-8')
    if f'## v{version}\n' not in old:
        path.write_text(old.replace('# Изменения\n','# Изменения\n\n'+notes.replace(f'# v{version} — русская озвучка Bugsnax',f'## v{version}')+'\n',1),encoding='utf-8')
    path=ROOT/'docs/voices.txt';cast=path.read_text(encoding='utf-8').split('Образцы:')[0].rstrip()
    if 'Сладколап' not in cast:cast+='\nСладколап — сдержанный мужской голос, деловой, осторожный и подозрительный.'
    path.write_text(cast+'\n\nВсе голоса включены в пакет озвучки.\n',encoding='utf-8')
    print('Prepared documentation for',count,'fragments and',voices,'voices.')

if __name__=='__main__':main()
