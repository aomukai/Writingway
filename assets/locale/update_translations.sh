#!/bin/bash

DOMAIN="writingway"
LOCALE_DIR="assets/locale"
POT_FILE="$LOCALE_DIR/$DOMAIN.pot"

# Extract strings
find . -maxdepth 2 -name "*.py" | xargs xgettext -d $DOMAIN -o $POT_FILE --keyword=_

# Update .po files
for lang in de es fr pt pl ru ja zh ko; do
    PO_FILE="$LOCALE_DIR/$lang/LC_MESSAGES/$DOMAIN.po"
    mkdir -p "$LOCALE_DIR/$lang/LC_MESSAGES"
    if [ -f "$PO_FILE" ]; then
        msgmerge --update "$PO_FILE" "$POT_FILE"
    else
        msginit -i "$POT_FILE" -o "$PO_FILE" -l $lang
    fi
    # Compile .mo file
    msgfmt "$PO_FILE" -o "${PO_FILE%.po}.mo"
done
