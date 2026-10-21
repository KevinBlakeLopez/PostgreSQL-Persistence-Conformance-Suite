package org.ppcs.hibernate;

import java.util.LinkedHashMap;
import java.util.Map;

import javax.sql.DataSource;

import org.hibernate.SessionFactory;
import org.hibernate.boot.MetadataSources;
import org.hibernate.boot.registry.StandardServiceRegistry;
import org.hibernate.boot.registry.StandardServiceRegistryBuilder;
import org.hibernate.boot.spi.SessionFactoryOptions;
import org.hibernate.cfg.AvailableSettings;
import org.hibernate.engine.spi.SessionFactoryImplementor;

/** Builds a native SessionFactory. Schema generation stays off. */
final class Boot {
    private Boot() {}

    static SessionFactory open(DataSource dataSource, SqlTrace sql, Map<String, Object> configuration) {
        StandardServiceRegistry registry = new StandardServiceRegistryBuilder()
                .applySetting(AvailableSettings.JAKARTA_NON_JTA_DATASOURCE, dataSource)
                .applySetting(AvailableSettings.HBM2DDL_AUTO, "none")
                .applySetting(AvailableSettings.JAKARTA_HBM2DDL_DATABASE_ACTION, "none")
                .applySetting(AvailableSettings.TRANSACTION_COORDINATOR_STRATEGY, "jdbc")
                .applySetting(AvailableSettings.CONNECTION_HANDLING, "DELAYED_ACQUISITION_AND_RELEASE_AFTER_TRANSACTION")
                .applySetting(AvailableSettings.JPA_COMPLIANCE, "false")
                .applySetting(AvailableSettings.JPA_TRANSACTION_COMPLIANCE, "false")
                .applySetting(AvailableSettings.SHOW_SQL, "false")
                .applySetting(AvailableSettings.FORMAT_SQL, "false")
                .applySetting(AvailableSettings.HIGHLIGHT_SQL, "false")
                .build();
        try {
            SessionFactory factory = new MetadataSources(registry)
                    .addAnnotatedClass(Item.class)
                    .addAnnotatedClass(Uniq.class)
                    .getMetadataBuilder()
                    .build()
                    .getSessionFactoryBuilder()
                    .applyStatementInspector(sql)
                    .build();
            // SessionFactory javadoc deprecates this as an SPI layer-breaker and says there is no plan to remove it.
            // It is the read-back of the options this factory was built with.
            @SuppressWarnings("deprecation")
            SessionFactoryOptions options = factory.getSessionFactoryOptions();
            configuration.put("dataSource", configuration.get("dataSource"));
            configuration.put("dialect", ((SessionFactoryImplementor) factory).getJdbcServices().getDialect().getClass().getName());
            configuration.put("hbm2ddlAuto", "none");
            configuration.put("schemaGenerationDatabaseAction", "none");
            configuration.put("transactionCoordinator", "jdbc");
            configuration.put("connectionHandling", String.valueOf(options.getPhysicalConnectionHandlingMode()));
            configuration.put("flushMode", String.valueOf(options.getInitialSessionFlushMode()));
            configuration.put("jpaBootstrap", options.isJpaBootstrap());
            configuration.put("jpaTransactionCompliance", options.getJpaCompliance().isJpaTransactionComplianceEnabled());
            configuration.put("connectionProviderDisablesAutoCommit", options.doesConnectionProviderDisableAutoCommit());
            configuration.put("autocommit", "Hibernate calls Connection.setAutoCommit(false) at begin when the provider has not disabled it, and setAutoCommit(true) in afterCompletion when it was on at begin");
            return factory;
        } catch (RuntimeException ex) {
            StandardServiceRegistryBuilder.destroy(registry);
            throw ex;
        }
    }
}
