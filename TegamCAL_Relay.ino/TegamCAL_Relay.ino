/*
 * TegamCAL_Relay.ino
 * Скетч для Arduino Nano Every (ATmega4809)
 * Управление 4-канальным релейным модулем для калибровщика Tegam 1750
 *
 * Версия: 1.1
 * Протокол: ASCII команды через USB Serial (9600 baud)
 *
 * ВНИМАНИЕ: Релейный модуль работает с ИНВЕРСНОЙ логикой!
 * LOW на пине = реле ВКЛЮЧЕНО, HIGH = ВЫКЛЮЧЕНО
 * Это инкапсулировано внутри функций — Python об этом не знает.
 *
 * Подключение пинов:
 *   D2 → In1 (реле 1, R1 = 2 Ом)
 *   D3 → In2 (реле 2, R2 = 20 Ом)
 *   D4 → In3 (реле 3, R3 = 200 Ом)
 *   D5 → In4 (реле 4, R4 = 2000 Ом)
 *
 * Команды (Python → Arduino):
 *   R0  → выключить все реле         → ответ: "OK"
 *   R1  → включить только реле 1     → ответ: "OK"
 *   R2  → включить только реле 2     → ответ: "OK"
 *   R3  → включить только реле 3     → ответ: "OK"
 *   R4  → включить только реле 4     → ответ: "OK"
 *   ?STS → статус (битовая маска)    → ответ: "STS:0001" (R4R3R2R1)
 *   ?ID  → идентификация             → ответ: "TegamCAL Arduino Nano Every v1.1"
 */

// Пины управления реле (соответствуют In1..In4 модуля)
const int RELAY_PINS[] = {2, 3, 4, 5};
const int NUM_RELAYS = 4;

// Текущее активное реле (0 = все выключены)
int activeRelay = 0;


// ---------------------------------------------------------------
// Вспомогательные функции
// ---------------------------------------------------------------

// Выключить все реле (установить HIGH из-за инверсной логики)
void allOff() {
  for (int i = 0; i < NUM_RELAYS; i++) {
    digitalWrite(RELAY_PINS[i], HIGH);
  }
  activeRelay = 0;
}

// Включить только одно реле (остальные выключить)
// point: 1..4
void activateRelay(int point) {
  allOff();  // сначала выключить все
  digitalWrite(RELAY_PINS[point - 1], LOW);  // включить нужное (LOW = ON)
  activeRelay = point;
}

// Сформировать строку статуса: "STS:0000" (битовая маска R4R3R2R1)
// Единица = реле включено
String buildStatusString() {
  String mask = "STS:";
  for (int i = NUM_RELAYS - 1; i >= 0; i--) {
    // Инверсная логика: LOW = включено, HIGH = выключено
    mask += (digitalRead(RELAY_PINS[i]) == LOW) ? "1" : "0";
  }
  return mask;
}


// ---------------------------------------------------------------
// setup() — выполняется один раз при старте / ресете
// ---------------------------------------------------------------
void setup() {
  // Инициализация пинов реле
  for (int i = 0; i < NUM_RELAYS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], HIGH);  // HIGH = выключено (инверсная логика)
  }

  // Запуск Serial
  Serial.begin(9600);
  while (!Serial) {
    ;  // ждём открытия порта (нужно для некоторых плат)
  }

  // Сообщение о готовности — Python ждёт строку с "Ready"
  Serial.println("TegamCAL Relay Module Ready");
}


// ---------------------------------------------------------------
// loop() — основной цикл, обработка команд
// ---------------------------------------------------------------
void loop() {
  if (Serial.available() > 0) {
    // Читаем команду до символа новой строки
    String command = Serial.readStringUntil('\n');
    command.trim();  // убрать \r и пробелы по краям

    // --- Команды управления реле ---
    if (command == "R0") {
      allOff();
      Serial.println("OK");

    } else if (command == "R1") {
      activateRelay(1);
      Serial.println("OK");

    } else if (command == "R2") {
      activateRelay(2);
      Serial.println("OK");

    } else if (command == "R3") {
      activateRelay(3);
      Serial.println("OK");

    } else if (command == "R4") {
      activateRelay(4);
      Serial.println("OK");

    // --- Запрос статуса ---
    } else if (command == "?STS") {
      Serial.println(buildStatusString());

    // --- Идентификация ---
    } else if (command == "?ID") {
      Serial.println("TegamCAL Arduino Nano Every v1.1");

    // --- Неизвестная команда ---
    } else {
      Serial.println("ERR:UNKNOWN_CMD");
    }
  }
}
