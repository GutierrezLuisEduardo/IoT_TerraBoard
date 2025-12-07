CREATE DATABASE IF NOT EXISTS iot_esp32;

USE iot_esp32;

-- Tabla con temperatura, humedad, nivel de agua y tiempo
CREATE TABLE IF NOT EXISTS registro_ambiente (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temperatura DECIMAL(5,2),
    humedad DECIMAL(5,2),
    nivel_agua DECIMAL(5,2),
    tiempo DATETIME
);

-- Tabla de promedios por minuto
CREATE TABLE IF NOT EXISTS promedios_por_minuto (
    id INT AUTO_INCREMENT PRIMARY KEY,
    minuto DATETIME NOT NULL UNIQUE,
    avg_temperatura DECIMAL(5,2),
    avg_humedad DECIMAL(5,2),
    avg_nivel_agua DECIMAL(5,2),
    conteo_registros INT NOT NULL DEFAULT 0,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tabla fija de rangos para c/animal

CREATE TABLE IF NOT EXISTS rangos_animales (
    id INT AUTO_INCREMENT PRIMARY KEY,
    Nombre VARCHAR(50) NOT NULL UNIQUE,
    minTemp DECIMAL(4,2) NOT NULL,
    maxTemp DECIMAL(4,2) NOT NULL,
    minHum  DECIMAL(4,2) NOT NULL,
    maxHum  DECIMAL(4,2) NOT NULL,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Registros específicos de c/animal
INSERT IGNORE INTO rangos_animales (Nombre, minTemp, maxTemp, minHum, maxHum) VALUES
('Tarántula',      22.00, 30.00, 60.00, 70.00),
('Jerbo',          20.00, 22.00, 30.00, 50.00),
('Dragón barbudo', 22.00, 40.00, 30.00, 40.00);

-- EVENT QUE SOLO GUARDA PROMEDIOS CUANDO EXISTEN REGISTROS
DELIMITER $$

DROP EVENT IF EXISTS calcular_promedios_minuto$$
CREATE EVENT calcular_promedios_minuto
ON SCHEDULE EVERY 1 MINUTE
STARTS CURRENT_TIMESTAMP + INTERVAL 30 SECOND      -- arranca a los :30 segundos de cada minuto
ON COMPLETION PRESERVE
DISABLE
DO
BEGIN
    SET @minuto_terminado = DATE_SUB(DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:00'), INTERVAL 1 MINUTE);

    -- Solo ejecutamos el INSERT/UPDATE si existe al menos 1 registro en ese minuto
    INSERT INTO promedios_por_minuto (
        minuto,
        avg_temperatura,
        avg_humedad,
        avg_nivel_agua,
        conteo_registros
    )
    SELECT
        @minuto_terminado,
        AVG(temperatura),
        AVG(humedad),
        AVG(nivel_agua),
        COUNT(*)
    FROM registro_ambiente
    WHERE tiempo >= @minuto_terminado
      AND tiempo <  @minuto_terminado + INTERVAL 1 MINUTE
    HAVING COUNT(*) > 0
    ON DUPLICATE KEY UPDATE
        avg_temperatura    = VALUES(avg_temperatura),
        avg_humedad        = VALUES(avg_humedad),
        avg_nivel_agua     = VALUES(avg_nivel_agua),
        conteo_registros   = VALUES(conteo_registros);

END$$

DELIMITER ;
