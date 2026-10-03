-- Projeto Atalaia v1 - Definição do Esquema de Banco de Dados
CREATE DATABASE IF NOT EXISTS atalaia_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE atalaia_db;

-- -------------------------------------------------------------
-- TABELA: locais
-- Armazena os ambientes e metadados de instalação dos sensores
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS locais (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(100) NOT NULL UNIQUE,
    descricao TEXT NULL,
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
-- TABELA: coletas
-- Registros brutos do DHT11 + variáveis físicas psicrométricas derivadas
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS coletas (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    local_id INT NOT NULL,
    uptime_sec INT UNSIGNED NOT NULL,
    temperatura DECIMAL(5, 2) NOT NULL COMMENT 'Temperatura (°C)',
    umidade DECIMAL(5, 2) NOT NULL COMMENT 'Umidade Relativa (%)',
    temperatura_kelvin DECIMAL(6, 2) NOT NULL COMMENT 'Temperatura (K)',
    pressao_vapor_sat DECIMAL(7, 3) NOT NULL COMMENT 'Pressão de Vapor de Saturação Es (hPa)',
    pressao_vapor_real DECIMAL(7, 3) NOT NULL COMMENT 'Pressão de Vapor Real Ea (hPa)',
    ponto_orvalho DECIMAL(5, 2) NOT NULL COMMENT 'Ponto de Orvalho (°C)',
    umidade_absoluta DECIMAL(6, 3) NOT NULL COMMENT 'Densidade de Vapor de Água (g/m³)',
    indice_calor DECIMAL(5, 2) NOT NULL COMMENT 'Sensação Térmica / Heat Index (°C)',
    coletado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_coletas_locais 
        FOREIGN KEY (local_id) REFERENCES locais(id) 
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Índices estratégicos para agregações temporais e filtros analíticos
CREATE INDEX idx_coletas_local_data ON coletas(local_id, coletado_em);
CREATE INDEX idx_coletas_metricas ON coletas(temperatura, umidade);