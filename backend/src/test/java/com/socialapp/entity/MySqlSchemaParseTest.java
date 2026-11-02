package com.socialapp.entity;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.FileSystemResource;
import org.springframework.jdbc.datasource.init.ScriptUtils;

import java.io.File;
import java.sql.Connection;
import java.sql.DriverManager;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;

class MySqlSchemaParseTest {

    @Test
    @DisplayName("Verify backend/schema.sql parses cleanly in MySQL mode")
    void testMySqlSchemaParsesCleanly() {
        assertDoesNotThrow(() -> {
            File schemaFile = new File("schema.sql");
            if (!schemaFile.exists()) {
                schemaFile = new File("backend/schema.sql");
            }

            try (Connection conn = DriverManager.getConnection("jdbc:h2:mem:mysql_schema_test;MODE=MySQL;DATABASE_TO_LOWER=TRUE", "sa", "")) {
                ScriptUtils.executeSqlScript(conn, new FileSystemResource(schemaFile));
            }
        });
    }
}
