package com.socialapp.entity;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties", properties = {
    "spring.jpa.hibernate.ddl-auto=validate"
})
class HibernateSchemaValidationTest {

    @Test
    @DisplayName("Verify Hibernate ddl-auto=validate succeeds without schema mismatch")
    void contextLoadsWithSchemaValidation() {
        // If there is any mismatch between JPA entities and schema-h2.sql,
        // the application context will fail to start during bean creation of EntityManagerFactory.
    }
}
