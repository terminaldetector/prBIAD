#!/usr/bin/env bash
#
# apply_fix_and_build.sh
#
# Распаковывает архив с исправлениями поверх локального клона репозитория,
# коммитит изменения, пушит в GitHub и (опционально) запускает workflow сборки.
#
# Использование:
#   ./apply_fix_and_build.sh <путь-к-локальному-репо> <путь-к-zip> [ветка]
#
# Пример:
#   ./apply_fix_and_build.sh ~/dev/gitShlak ~/Downloads/gitShlak-buildable.zip feature/unified-chat-with-rag
#
# Требования:
#   - git должен быть установлен и репозиторий уже склонирован (git clone ...)
#   - unzip должен быть установлен
#   - (опционально) GitHub CLI `gh`, залогиненный (`gh auth login`), чтобы
#     скрипт сам запустил workflow и открыл ссылку на прогон в Actions.
#     Без gh просто push в ветку тоже запустит workflow (он висит на
#     push/pull_request/workflow_dispatch).

set -euo pipefail

REPO_DIR="${1:?Укажите путь к локальному клону репозитория (первый аргумент)}"
ZIP_PATH="${2:?Укажите путь к архиву gitShlak-buildable.zip (второй аргумент)}"
BRANCH="${3:-feature/unified-chat-with-rag}"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "❌ '$REPO_DIR' — это не git-репозиторий. Сначала сделайте:"
    echo "   git clone https://github.com/hren4073-cpu/gitShlak.git \"$REPO_DIR\""
    exit 1
fi

if [ ! -f "$ZIP_PATH" ]; then
    echo "❌ Архив не найден: $ZIP_PATH"
    exit 1
fi

command -v unzip >/dev/null || { echo "❌ Нужен unzip (sudo apt install unzip)"; exit 1; }
command -v git   >/dev/null || { echo "❌ Нужен git"; exit 1; }

echo "▶ Распаковываю архив во временную папку..."
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
unzip -q "$ZIP_PATH" -d "$TMP_DIR"

# Внутри архива один корневой каталог (например gitShlak-feature-unified-chat-with-rag).
# Найдём его и будем копировать именно его содержимое, а не сам каталог.
INNER_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "$INNER_DIR" ]; then
    echo "❌ Не удалось найти корневую папку внутри архива"
    exit 1
fi
echo "  Найдена папка: $(basename "$INNER_DIR")"

cd "$REPO_DIR"

echo "▶ Переключаюсь на ветку $BRANCH (создам, если её ещё нет)..."
git fetch origin "$BRANCH" 2>/dev/null || true
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git checkout "$BRANCH"
    git pull origin "$BRANCH" --ff-only 2>/dev/null || true
elif git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    git checkout -b "$BRANCH" "origin/$BRANCH"
else
    git checkout -b "$BRANCH"
fi

echo "▶ Копирую файлы из архива поверх репозитория..."
# -a сохраняет права/структуру, rsync лучше cp тем, что не трогает .git и
# аккуратно перезаписывает существующие файлы.
if command -v rsync >/dev/null; then
    rsync -a "$INNER_DIR"/ "$REPO_DIR"/ --exclude ".git"
else
    cp -a "$INNER_DIR"/. "$REPO_DIR"/
fi

echo "▶ Проверяю, есть ли изменения..."
if git diff --quiet && git diff --cached --quiet && [ -z "$(git status --porcelain)" ]; then
    echo "  Изменений нет — репозиторий уже актуален."
else
    git add -A
    git commit -m "Fix build: missing gradle skeleton, duplicate classes, broken layouts"
    echo "▶ Пушу в origin/$BRANCH..."
    git push -u origin "$BRANCH"
fi

REPO_URL="$(git config --get remote.origin.url | sed -E 's#git@github.com:#https://github.com/#; s#\.git$##')"

if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    echo "▶ Запускаю workflow вручную через gh CLI..."
    gh workflow run main.yml --ref "$BRANCH" || echo "  (workflow_dispatch не сработал — ничего страшного, push уже должен был его запустить)"
    sleep 3
    echo "▶ Открываю список прогонов..."
    gh run list --branch "$BRANCH" --limit 5 || true
    echo ""
    echo "Смотреть тут: $REPO_URL/actions"
else
    echo ""
    echo "ℹ️  GitHub CLI (gh) не найден/не залогинен — просто открой Actions в браузере,"
    echo "   push в ветку уже должен был запустить сборку:"
    echo "   $REPO_URL/actions"
fi

echo ""
echo "✅ Готово."
