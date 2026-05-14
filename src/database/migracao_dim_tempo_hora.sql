-- ==========================================================
-- Migracao BI: criacao de dimensoes de tempo e hora
-- Projeto: clima-project
-- Banco: Oracle
-- ==========================================================
-- Objetivo:
-- 1) Criar DIM_TEMPO (dia, mes, ano etc.)
-- 2) Criar DIM_HORA_MINUTO (24 horas em granularidade de minuto)
-- 3) Alterar FATO_CLIMA para usar chaves de tempo/hora
-- 4) Popular dados existentes e criar relacionamentos
-- ==========================================================

SET DEFINE OFF;

PROMPT [1/7] Criando DIM_TEMPO se nao existir...
DECLARE
  v_exists NUMBER := 0;
BEGIN
  SELECT COUNT(*)
    INTO v_exists
    FROM user_tables
   WHERE table_name = 'DIM_TEMPO';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE q'[
      CREATE TABLE DIM_TEMPO (
        TEMPO_ID           NUMBER(8)      NOT NULL,
        DATA_COMPLETA      DATE           NOT NULL,
        DIA_NUMERO         NUMBER(2)      NOT NULL,
        DIA_NOME           VARCHAR2(20)   NOT NULL,
        DIA_SEMANA_NUMERO  NUMBER(1)      NOT NULL,
        EH_FIM_SEMANA      NUMBER(1)      NOT NULL,
        MES_NUMERO         NUMBER(2)      NOT NULL,
        MES_NOME           VARCHAR2(20)   NOT NULL,
        TRIMESTRE_NUMERO   NUMBER(1)      NOT NULL,
        SEMESTRE_NUMERO    NUMBER(1)      NOT NULL,
        ANO_NUMERO         NUMBER(4)      NOT NULL,
        ANO_MES            CHAR(7)        NOT NULL,
        CONSTRAINT PK_DIM_TEMPO PRIMARY KEY (TEMPO_ID),
        CONSTRAINT UK_DIM_TEMPO_DATA UNIQUE (DATA_COMPLETA)
      )
    ]';
  END IF;
END;
/

PROMPT [2/7] Criando DIM_HORA_MINUTO se nao existir...
DECLARE
  v_exists NUMBER := 0;
BEGIN
  SELECT COUNT(*)
    INTO v_exists
    FROM user_tables
   WHERE table_name = 'DIM_HORA_MINUTO';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE q'[
      CREATE TABLE DIM_HORA_MINUTO (
        HORA_MINUTO_ID     NUMBER(4)      NOT NULL,
        HORA_NUMERO        NUMBER(2)      NOT NULL,
        MINUTO_NUMERO      NUMBER(2)      NOT NULL,
        HORA_MINUTO_TXT    CHAR(5)        NOT NULL,
        TURNO              VARCHAR2(20)   NOT NULL,
        CONSTRAINT PK_DIM_HORA_MINUTO PRIMARY KEY (HORA_MINUTO_ID)
      )
    ]';
  END IF;
END;
/

PROMPT [3/7] Populando DIM_HORA_MINUTO (00:00 ate 23:59)...
MERGE INTO DIM_HORA_MINUTO d
USING (
  SELECT
    LEVEL AS hora_minuto_id,
    FLOOR((LEVEL - 1) / 60) AS hora_numero,
    MOD(LEVEL - 1, 60) AS minuto_numero,
    LPAD(FLOOR((LEVEL - 1) / 60), 2, '0') || ':' || LPAD(MOD(LEVEL - 1, 60), 2, '0') AS hora_minuto_txt,
    CASE
      WHEN FLOOR((LEVEL - 1) / 60) BETWEEN 0 AND 5 THEN 'MADRUGADA'
      WHEN FLOOR((LEVEL - 1) / 60) BETWEEN 6 AND 11 THEN 'MANHA'
      WHEN FLOOR((LEVEL - 1) / 60) BETWEEN 12 AND 17 THEN 'TARDE'
      ELSE 'NOITE'
    END AS turno
  FROM dual
  CONNECT BY LEVEL <= 1440
) s
ON (d.HORA_MINUTO_ID = s.hora_minuto_id)
WHEN MATCHED THEN UPDATE SET
  d.HORA_NUMERO = s.hora_numero,
  d.MINUTO_NUMERO = s.minuto_numero,
  d.HORA_MINUTO_TXT = s.hora_minuto_txt,
  d.TURNO = s.turno
WHEN NOT MATCHED THEN INSERT (
  HORA_MINUTO_ID,
  HORA_NUMERO,
  MINUTO_NUMERO,
  HORA_MINUTO_TXT,
  TURNO
) VALUES (
  s.hora_minuto_id,
  s.hora_numero,
  s.minuto_numero,
  s.hora_minuto_txt,
  s.turno
);

PROMPT [4/7] Populando DIM_TEMPO com base em FATO_CLIMA...
DECLARE
  v_data_min DATE;
  v_data_max DATE;
BEGIN
  SELECT TRUNC(MIN(DATA_COLETA)), TRUNC(MAX(DATA_COLETA))
    INTO v_data_min, v_data_max
    FROM FATO_CLIMA
   WHERE DATA_COLETA IS NOT NULL;

  IF v_data_min IS NULL OR v_data_max IS NULL THEN
    DBMS_OUTPUT.PUT_LINE('DIM_TEMPO: sem DATA_COLETA valida em FATO_CLIMA. Nenhuma linha gerada.');
  ELSE
    MERGE /*+ NO_PARALLEL */ INTO DIM_TEMPO d
    USING (
      SELECT v_data_min + LEVEL - 1 AS dt
        FROM dual
      CONNECT BY LEVEL <= (v_data_max - v_data_min + 1)
    ) s
    ON (d.TEMPO_ID = TO_NUMBER(TO_CHAR(s.dt, 'YYYYMMDD')))
    WHEN MATCHED THEN UPDATE SET
      d.DATA_COMPLETA = s.dt,
      d.DIA_NUMERO = TO_NUMBER(TO_CHAR(s.dt, 'DD')),
      d.DIA_NOME = INITCAP(TO_CHAR(s.dt, 'FMDAY', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
      d.DIA_SEMANA_NUMERO = (TRUNC(s.dt) - TRUNC(s.dt, 'IW') + 1),
      d.EH_FIM_SEMANA = CASE WHEN (TRUNC(s.dt) - TRUNC(s.dt, 'IW') + 1) IN (6, 7) THEN 1 ELSE 0 END,
      d.MES_NUMERO = TO_NUMBER(TO_CHAR(s.dt, 'MM')),
      d.MES_NOME = INITCAP(TO_CHAR(s.dt, 'FMMONTH', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
      d.TRIMESTRE_NUMERO = TO_NUMBER(TO_CHAR(s.dt, 'Q')),
      d.SEMESTRE_NUMERO = CASE WHEN TO_NUMBER(TO_CHAR(s.dt, 'MM')) <= 6 THEN 1 ELSE 2 END,
      d.ANO_NUMERO = TO_NUMBER(TO_CHAR(s.dt, 'YYYY')),
      d.ANO_MES = TO_CHAR(s.dt, 'YYYY-MM')
    WHEN NOT MATCHED THEN INSERT (
      TEMPO_ID,
      DATA_COMPLETA,
      DIA_NUMERO,
      DIA_NOME,
      DIA_SEMANA_NUMERO,
      EH_FIM_SEMANA,
      MES_NUMERO,
      MES_NOME,
      TRIMESTRE_NUMERO,
      SEMESTRE_NUMERO,
      ANO_NUMERO,
      ANO_MES
    ) VALUES (
      TO_NUMBER(TO_CHAR(s.dt, 'YYYYMMDD')),
      s.dt,
      TO_NUMBER(TO_CHAR(s.dt, 'DD')),
      INITCAP(TO_CHAR(s.dt, 'FMDAY', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
      (TRUNC(s.dt) - TRUNC(s.dt, 'IW') + 1),
      CASE WHEN (TRUNC(s.dt) - TRUNC(s.dt, 'IW') + 1) IN (6, 7) THEN 1 ELSE 0 END,
      TO_NUMBER(TO_CHAR(s.dt, 'MM')),
      INITCAP(TO_CHAR(s.dt, 'FMMONTH', 'NLS_DATE_LANGUAGE=PORTUGUESE')),
      TO_NUMBER(TO_CHAR(s.dt, 'Q')),
      CASE WHEN TO_NUMBER(TO_CHAR(s.dt, 'MM')) <= 6 THEN 1 ELSE 2 END,
      TO_NUMBER(TO_CHAR(s.dt, 'YYYY')),
      TO_CHAR(s.dt, 'YYYY-MM')
    );
  END IF;
END;
/

PROMPT [5/7] Alterando FATO_CLIMA para incluir chaves de tempo/hora...
DECLARE
  v_exists NUMBER := 0;
BEGIN
  SELECT COUNT(*)
    INTO v_exists
    FROM user_tab_cols
   WHERE table_name = 'FATO_CLIMA'
     AND column_name = 'TEMPO_ID';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE FATO_CLIMA ADD (TEMPO_ID NUMBER(8))';
  END IF;

  SELECT COUNT(*)
    INTO v_exists
    FROM user_tab_cols
   WHERE table_name = 'FATO_CLIMA'
     AND column_name = 'HORA_MINUTO_ID';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE FATO_CLIMA ADD (HORA_MINUTO_ID NUMBER(4))';
  END IF;
END;
/

PROMPT [6/7] Preenchendo novas chaves na FATO_CLIMA...
UPDATE FATO_CLIMA
   SET TEMPO_ID = TO_NUMBER(TO_CHAR(DATA_COLETA, 'YYYYMMDD')),
       HORA_MINUTO_ID = (TO_NUMBER(TO_CHAR(DATA_COLETA, 'HH24')) * 60) + TO_NUMBER(TO_CHAR(DATA_COLETA, 'MI')) + 1
 WHERE DATA_COLETA IS NOT NULL
   AND (TEMPO_ID IS NULL OR HORA_MINUTO_ID IS NULL);

PROMPT [7/7] Criando indices e FKs (se nao existirem)...
DECLARE
  v_exists NUMBER := 0;
BEGIN
  SELECT COUNT(*)
    INTO v_exists
    FROM user_indexes
   WHERE index_name = 'IDX_FATO_CLIMA_TEMPO';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE INDEX IDX_FATO_CLIMA_TEMPO ON FATO_CLIMA (TEMPO_ID)';
  END IF;

  SELECT COUNT(*)
    INTO v_exists
    FROM user_indexes
   WHERE index_name = 'IDX_FATO_CLIMA_HORA';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE INDEX IDX_FATO_CLIMA_HORA ON FATO_CLIMA (HORA_MINUTO_ID)';
  END IF;

  SELECT COUNT(*)
    INTO v_exists
    FROM user_constraints
   WHERE constraint_name = 'FK_FATO_CLIMA_DIM_TEMPO';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE q'[
      ALTER TABLE FATO_CLIMA
      ADD CONSTRAINT FK_FATO_CLIMA_DIM_TEMPO
      FOREIGN KEY (TEMPO_ID)
      REFERENCES DIM_TEMPO (TEMPO_ID)
    ]';
  END IF;

  SELECT COUNT(*)
    INTO v_exists
    FROM user_constraints
   WHERE constraint_name = 'FK_FATO_CLIMA_DIM_HORA';

  IF v_exists = 0 THEN
    EXECUTE IMMEDIATE q'[
      ALTER TABLE FATO_CLIMA
      ADD CONSTRAINT FK_FATO_CLIMA_DIM_HORA
      FOREIGN KEY (HORA_MINUTO_ID)
      REFERENCES DIM_HORA_MINUTO (HORA_MINUTO_ID)
    ]';
  END IF;
END;
/

COMMIT;

PROMPT ===============================================
PROMPT Migracao concluida.
PROMPT Observacao: apos validar o BI, voce pode avaliar remover DATA_COLETA da fato.
PROMPT Exemplo: ALTER TABLE FATO_CLIMA DROP COLUMN DATA_COLETA;
PROMPT ===============================================
