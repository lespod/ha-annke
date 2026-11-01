#!/usr/bin/env python3
"""Generate strings.json and translations/{en,pl,de}.json for the Annke integration.

Every text lives once here as (English, Polish, German), so the three
languages cannot drift apart. Run after changing entity keys.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "annke"
LANGS = ("en", "pl", "de")

# Entity names. Each also gets a "<key>_channel" variant for multi-lens cameras.
ENTITIES = {
    "switch": {
        "white_light": ("White light", "Biała dioda", "Weißlicht"),
        "motion_detection": ("Motion detection", "Wykrywanie ruchu", "Bewegungserkennung"),
        "tamper_detection": ("Tamper detection", "Wykrywanie sabotażu", "Sabotageerkennung"),
        "intrusion_detection": ("Intrusion detection", "Wykrywanie wtargnięcia", "Einbruchserkennung"),
        "line_crossing_detection": ("Line crossing detection", "Wykrywanie przekroczenia linii", "Linienüberschreitung"),
        "region_entrance_detection": ("Region entrance detection", "Wykrywanie wejścia do strefy", "Bereichseintritt"),
        "region_exiting_detection": ("Region exiting detection", "Wykrywanie wyjścia ze strefy", "Bereichsaustritt"),
        "scene_change_detection": ("Scene change detection", "Wykrywanie zmiany sceny", "Szenenwechselerkennung"),
        "defocus_detection": ("Defocus detection", "Wykrywanie utraty ostrości", "Defokussierungserkennung"),
        "audio_exception_detection": ("Audio exception detection", "Wykrywanie anomalii dźwięku", "Audio-Ausnahmeerkennung"),
        "privacy_mask": ("Privacy mask", "Maska prywatności", "Privatzonenmaskierung"),
        "image_flip": ("Image flip", "Odwrócenie obrazu", "Bild spiegeln"),
    },
    "select": {
        "supplement_light_mode": ("Supplement light mode", "Tryb doświetlenia", "Zusatzlichtmodus"),
        "light_brightness_mode": ("Light brightness control", "Sterowanie jasnością doświetlenia", "Helligkeitssteuerung"),
        "day_night_mode": ("Day/night mode", "Tryb dzień/noc", "Tag-/Nachtmodus"),
        "wdr_mode": ("WDR", "WDR", "WDR"),
        "strobe_frequency": ("Strobe frequency", "Częstotliwość stroboskopu", "Blitzfrequenz"),
        "siren_sound": ("Siren sound", "Dźwięk syreny", "Sirenenton"),
    },
    "number": {
        "white_light_brightness": ("White light brightness", "Jasność białej diody", "Weißlicht-Helligkeit"),
        "ir_light_brightness": ("IR brightness", "Jasność podczerwieni", "IR-Helligkeit"),
        "white_light_brightness_limit": ("White light brightness limit", "Limit jasności białej diody", "Weißlicht-Helligkeitsgrenze"),
        "day_night_sensitivity": ("Day/night sensitivity", "Czułość dzień/noc", "Tag-/Nacht-Empfindlichkeit"),
        "day_night_delay": ("Day/night switch delay", "Opóźnienie przełączania dzień/noc", "Tag-/Nacht-Umschaltverzögerung"),
        "strobe_duration": ("Strobe duration", "Czas stroboskopu", "Blitzdauer"),
        "siren_volume": ("Siren volume", "Głośność syreny", "Sirenenlautstärke"),
        "siren_repeats": ("Siren repeats", "Powtórzenia syreny", "Sirenenwiederholungen"),
    },
    "binary_sensor": {
        "motion": ("Motion", "Ruch", "Bewegung"),
        "human": ("Person", "Osoba", "Person"),
        "vehicle": ("Vehicle", "Pojazd", "Fahrzeug"),
        "intrusion": ("Intrusion", "Wtargnięcie", "Einbruch"),
        "line_crossing": ("Line crossing", "Przekroczenie linii", "Linienüberschreitung"),
        "region_entrance": ("Region entrance", "Wejście do strefy", "Bereichseintritt"),
        "region_exiting": ("Region exiting", "Wyjście ze strefy", "Bereichsaustritt"),
        "tamper": ("Tampering", "Sabotaż", "Sabotage"),
        "scene_change": ("Scene change", "Zmiana sceny", "Szenenwechsel"),
        "defocus": ("Defocus", "Utrata ostrości", "Defokussierung"),
        "audio_exception": ("Audio exception", "Anomalia dźwięku", "Audio-Ausnahme"),
        "pir": ("PIR", "PIR", "PIR"),
        "event_stream": ("Event connection", "Połączenie zdarzeń", "Ereignisverbindung"),
    },
    "sensor": {
        "cpu": ("CPU usage", "Użycie CPU", "CPU-Auslastung"),
        "memory": ("Memory usage", "Użycie pamięci", "Speicherauslastung"),
        "boot_time": ("Last boot", "Ostatnie uruchomienie", "Letzter Start"),
        "storage_status": ("SD card status", "Stan karty SD", "SD-Karten-Status"),
        "storage_free": ("SD card free space", "Wolne miejsce na karcie SD", "Freier SD-Speicher"),
        "storage_capacity": ("SD card capacity", "Pojemność karty SD", "SD-Karten-Kapazität"),
    },
    "button": {
        "reboot": ("Reboot", "Uruchom ponownie", "Neu starten"),
        "enable_event_linkage": ("Enable event notifications", "Włącz powiadomienia o zdarzeniach", "Ereignisbenachrichtigungen aktivieren"),
        "siren_test": ("Play siren", "Odtwórz syrenę", "Sirene abspielen"),
        "wiper": ("Wiper", "Wycieraczka", "Wischer"),
        "focus": ("Auto focus", "Autofokus", "Autofokus"),
    },
    "camera": {
        "main_stream": ("Main stream", "Strumień główny", "Hauptstream"),
        "sub_stream": ("Sub stream", "Strumień pomocniczy", "Substream"),
    },
}

# Entities with their own placeholder instead of a channel variant.
PORT_ENTITIES = {
    "switch": {"alarm_output": ("Alarm output {port}", "Wyjście alarmowe {port}", "Alarmausgang {port}")},
    "binary_sensor": {"alarm_input": ("Alarm input {port}", "Wejście alarmowe {port}", "Alarmeingang {port}")},
}

CHANNEL_SUFFIX = (" (lens {channel})", " (obiektyw {channel})", " (Objektiv {channel})")

SELECT_STATES = {
    "color_vu_white_light": ("White light", "Biała dioda", "Weißlicht"),
    "ir_light": ("Infrared", "Podczerwień", "Infrarot"),
    "event_intelligence": ("Smart (on event)", "Inteligentne (przy zdarzeniu)", "Intelligent (bei Ereignis)"),
    "close": ("Off", "Wyłączone", "Aus"),
    "auto": ("Auto", "Automatycznie", "Automatisch"),
    "manual": ("Manual", "Ręcznie", "Manuell"),
    "day": ("Day", "Dzień", "Tag"),
    "night": ("Night", "Noc", "Nacht"),
    "schedule": ("Schedule", "Harmonogram", "Zeitplan"),
    "event_trigger": ("Event trigger", "Wyzwalanie zdarzeniem", "Ereignisauslösung"),
    "open": ("On", "Włączone", "Ein"),
    "high": ("High", "Wysoka", "Hoch"),
    "medium": ("Medium", "Średnia", "Mittel"),
    "low": ("Low", "Niska", "Niedrig"),
    "normally_on": ("Always on", "Ciągłe światło", "Dauerlicht"),
}
SELECTS_WITH_STATES = (
    "supplement_light_mode",
    "light_brightness_mode",
    "day_night_mode",
    "wdr_mode",
    "strobe_frequency",
)

CONFIG = {
    "user_title": ("Add Annke camera", "Dodaj kamerę Annke", "Annke-Kamera hinzufügen"),
    "user_desc": (
        "Enter the camera address and an account on the camera. A separate user with the Operator role is recommended.",
        "Podaj adres kamery i konto w kamerze. Zalecany jest osobny użytkownik z rolą Operator.",
        "Gib die Kameraadresse und ein Kamerakonto ein. Empfohlen wird ein eigener Benutzer mit der Rolle Operator.",
    ),
    "reauth_title": ("Sign in again", "Zaloguj się ponownie", "Erneut anmelden"),
    "reauth_desc": (
        "The camera at {host} rejected the saved password.",
        "Kamera pod adresem {host} odrzuciła zapisane hasło.",
        "Die Kamera unter {host} hat das gespeicherte Passwort abgelehnt.",
    ),
    "reconf_title": ("Change camera address", "Zmień adres kamery", "Kameraadresse ändern"),
    "host": ("Host", "Adres", "Host"),
    "keep_password": ("Leave empty to keep the saved password.", "Zostaw puste, aby zachować zapisane hasło.", "Leer lassen, um das gespeicherte Passwort zu behalten."),
    "username": ("Username", "Login", "Benutzername"),
    "password": ("Password", "Hasło", "Passwort"),
    "port": ("HTTP port", "Port HTTP", "HTTP-Port"),
    "ssl": ("Use HTTPS", "Użyj HTTPS", "HTTPS verwenden"),
    "host_desc": ("IP address or hostname of the camera.", "Adres IP lub nazwa hosta kamery.", "IP-Adresse oder Hostname der Kamera."),
    "cannot_connect": ("Cannot connect to the camera.", "Nie można połączyć się z kamerą.", "Keine Verbindung zur Kamera."),
    "invalid_auth": ("Wrong username or password.", "Nieprawidłowy login lub hasło.", "Falscher Benutzername oder falsches Passwort."),
    "already_configured": ("This camera is already configured.", "Ta kamera jest już dodana.", "Diese Kamera ist bereits eingerichtet."),
    "reauth_successful": ("Signed in again.", "Zalogowano ponownie.", "Erneut angemeldet."),
    "reconfigure_successful": ("Camera updated.", "Zaktualizowano kamerę.", "Kamera aktualisiert."),
    "unique_id_mismatch": (
        "This is a different camera (serial number does not match).",
        "To inna kamera (numer seryjny się nie zgadza).",
        "Das ist eine andere Kamera (Seriennummer stimmt nicht überein).",
    ),
    "options_title": ("Event settings", "Ustawienia zdarzeń", "Ereigniseinstellungen"),
    "off_delay": ("Event off delay (s)", "Czas wygaszania zdarzenia (s)", "Ereignis-Abschaltverzögerung (s)"),
    "off_delay_desc": (
        "How long a detection stays on after the camera's last alert.",
        "Jak długo wykrycie pozostaje aktywne po ostatnim alercie z kamery.",
        "Wie lange eine Erkennung nach der letzten Meldung der Kamera aktiv bleibt.",
    ),
    "issue_title": (
        "{name}: some events are not sent to Home Assistant",
        "{name}: część zdarzeń nie trafia do Home Assistant",
        "{name}: Einige Ereignisse werden nicht an Home Assistant gesendet",
    ),
    "issue_desc": (
        "These camera events do not have \"Notify Surveillance Center\" enabled, so their sensors will never turn on: {events}.\n\nPress the \"Enable event notifications\" button on the device page, or enable it in the camera's web interface under Event → Linkage Action.",
        "Te zdarzenia w kamerze nie mają włączonej opcji „Powiadom centrum monitoringu”, więc ich czujniki nigdy się nie włączą: {events}.\n\nNaciśnij przycisk „Włącz powiadomienia o zdarzeniach” na stronie urządzenia albo włącz tę opcję w panelu kamery w Zdarzenie → Akcja powiązania.",
        "Für diese Kameraereignisse ist „Überwachungszentrale benachrichtigen“ nicht aktiviert, daher schalten ihre Sensoren nie ein: {events}.\n\nDrücke die Taste „Ereignisbenachrichtigungen aktivieren“ auf der Geräteseite oder aktiviere die Option in der Weboberfläche der Kamera unter Ereignis → Verknüpfungsaktion.",
    ),
    "forbidden": (
        "{name}: the camera account is not allowed to change settings (HTTP 403). In the camera, give this user the \"Remote: Parameters Settings\" permission, or use an administrator account.",
        "{name}: konto w kamerze nie może zmieniać ustawień (HTTP 403). W kamerze nadaj temu użytkownikowi uprawnienie „Zdalne: ustawienia parametrów” albo użyj konta administratora.",
        "{name}: Das Kamerakonto darf keine Einstellungen ändern (HTTP 403). Gib diesem Benutzer in der Kamera die Berechtigung „Fernzugriff: Parametereinstellungen“ oder verwende ein Administratorkonto.",
    ),
    "unknown_device": ("This device is not an Annke camera.", "To urządzenie nie jest kamerą Annke.", "Dieses Gerät ist keine Annke-Kamera."),
    "no_ptz": ("{name} does not support PTZ on this channel.", "{name} nie obsługuje PTZ na tym kanale.", "{name} unterstützt kein PTZ auf diesem Kanal."),
    "svc_ptz": ("PTZ move", "Ruch PTZ", "PTZ-Bewegung"),
    "svc_ptz_desc": (
        "Pan, tilt or zoom the camera for a short time.",
        "Obróć, pochyl lub przybliż kamerę przez krótki czas.",
        "Kamera kurz schwenken, neigen oder zoomen.",
    ),
    "svc_preset": ("Go to preset", "Przejdź do presetu", "Zu Preset fahren"),
    "svc_preset_desc": ("Move the camera to a saved position.", "Ustaw kamerę w zapisanej pozycji.", "Kamera auf eine gespeicherte Position fahren."),
    "device": ("Camera", "Kamera", "Kamera"),
    "channel": ("Channel", "Kanał", "Kanal"),
    "pan": ("Pan speed", "Prędkość obrotu", "Schwenkgeschwindigkeit"),
    "tilt": ("Tilt speed", "Prędkość pochylenia", "Neigegeschwindigkeit"),
    "zoom": ("Zoom speed", "Prędkość zoomu", "Zoomgeschwindigkeit"),
    "duration": ("Duration (s)", "Czas (s)", "Dauer (s)"),
    "preset": ("Preset number", "Numer presetu", "Preset-Nummer"),
    "speed_desc": ("-100 to 100; negative values move the other way.", "Od -100 do 100; wartości ujemne to ruch w przeciwną stronę.", "-100 bis 100; negative Werte bewegen in die Gegenrichtung."),
}


def build(i: int) -> dict:
    t = {k: v[i] for k, v in CONFIG.items()}
    entity: dict = {}
    for platform, items in ENTITIES.items():
        out = entity.setdefault(platform, {})
        for key, names in items.items():
            out[key] = {"name": names[i]}
            out[f"{key}_channel"] = {"name": names[i] + CHANNEL_SUFFIX[i]}
            if platform == "select" and key in SELECTS_WITH_STATES:
                states = {s: v[i] for s, v in SELECT_STATES.items()}
                out[key]["state"] = states
                out[f"{key}_channel"]["state"] = states
    for platform, items in PORT_ENTITIES.items():
        for key, names in items.items():
            entity[platform][key] = {"name": names[i]}

    data = {
        "config": {
            "step": {
                "user": {
                    "title": t["user_title"],
                    "description": t["user_desc"],
                    "data": {k: t[k] for k in ("host", "username", "password", "port", "ssl")},
                    "data_description": {"host": t["host_desc"]},
                },
                "reauth_confirm": {
                    "title": t["reauth_title"],
                    "description": t["reauth_desc"],
                    "data": {k: t[k] for k in ("username", "password")},
                },
                "reconfigure": {
                    "title": t["reconf_title"],
                    "data": {k: t[k] for k in ("host", "username", "password", "port", "ssl")},
                    "data_description": {"password": t["keep_password"]},
                },
            },
            "error": {k: t[k] for k in ("cannot_connect", "invalid_auth")},
            "abort": {
                k: t[k]
                for k in ("already_configured", "reauth_successful", "reconfigure_successful", "unique_id_mismatch")
            },
        },
        "options": {
            "step": {
                "init": {
                    "title": t["options_title"],
                    "data": {"off_delay": t["off_delay"]},
                    "data_description": {"off_delay": t["off_delay_desc"]},
                }
            }
        },
        "entity": entity,
        "issues": {"missing_linkage": {"title": t["issue_title"], "description": t["issue_desc"]}},
        "exceptions": {
            "unknown_device": {"message": t["unknown_device"]},
            "no_ptz": {"message": t["no_ptz"]},
            "forbidden": {"message": t["forbidden"]},
        },
        "services": {
            "ptz_move": {
                "name": t["svc_ptz"],
                "description": t["svc_ptz_desc"],
                "fields": {
                    "device_id": {"name": t["device"], "description": t["device"]},
                    "channel": {"name": t["channel"], "description": t["channel"]},
                    "pan": {"name": t["pan"], "description": t["speed_desc"]},
                    "tilt": {"name": t["tilt"], "description": t["speed_desc"]},
                    "zoom": {"name": t["zoom"], "description": t["speed_desc"]},
                    "duration": {"name": t["duration"], "description": t["duration"]},
                },
            },
            "goto_preset": {
                "name": t["svc_preset"],
                "description": t["svc_preset_desc"],
                "fields": {
                    "device_id": {"name": t["device"], "description": t["device"]},
                    "channel": {"name": t["channel"], "description": t["channel"]},
                    "preset": {"name": t["preset"], "description": t["preset"]},
                },
            },
        },
    }
    return data


def main() -> None:
    (ROOT / "translations").mkdir(exist_ok=True)
    for i, lang in enumerate(LANGS):
        text = json.dumps(build(i), ensure_ascii=False, indent=2) + "\n"
        (ROOT / "translations" / f"{lang}.json").write_text(text, encoding="utf-8")
        if lang == "en":
            (ROOT / "strings.json").write_text(text, encoding="utf-8")
    print("written:", ", ".join(LANGS))


if __name__ == "__main__":
    main()
