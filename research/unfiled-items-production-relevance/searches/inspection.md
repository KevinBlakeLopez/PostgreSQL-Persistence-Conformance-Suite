Written by: GPT-6 / Codex (effort setting not exposed).

# Inspected code sample, 2026-10-26

These are convenience samples of GitHub legacy code-search hits, read at the commits linked. They are not random samples or installed-deployment counts. Classification is of the inspected file and explicitly noted supporting files; untraced callers and configuration remain unknown. Nothing was executed. No exposure claim below relies only on a search fragment.

## Laravel F1

| File at commit | Inspection |
| --- | --- |
| [src/Form.php](https://github.com/z-song/laravel-admin/blob/67c441eb78ecc5437e59775d89770cd9c2cb1e05/src/Form.php#L336) | No caught nested unit in the inspected store/update transactions. |
| [src/Models/Cart.php](https://github.com/conedevelopment/bazar/blob/32bc97a593915ca40e1323239b6ffd9582aa2f5f/src/Models/Cart.php#L213) | Latent helper: transaction failure is swallowed; an outer committing caller and earlier nested writes were not traced. |
| [src/Import.php](https://github.com/konnco/filament-import/blob/c9963f09762144f90c4965579785f41ff8a07aac/src/Import.php#L154) | One transaction around import; no established caught nested transaction. |
| [models/Order.php](https://github.com/OFFLINE-GmbH/oc-mall-plugin/blob/d381ddcfe95c048fc11a69c5f7c5dde27ee88dac/models/Order.php#L193) | Separate transaction call sites; no established catch between nested units. |
| [src/Models/Tier.php](https://github.com/cjmellor/level-up/blob/e6091fa4e0c92ff58843c46bb9b4ebab0ad679d1/src/Models/Tier.php#L66) | Unique error is converted and rethrown. |
| [app/Jobs/ArticleDetail.php](https://github.com/simon-8/story/blob/e72dc211d5d66855a0ba361edffe56808e2f3f2c/app/Jobs/ArticleDetail.php#L58) | Catches inside a single transaction before its first successful write; no nested unit. |
| [src/Order/Order.php](https://github.com/mollie/laravel-cashier-mollie/blob/c10df7845561969dd716dd98a9632e8139280dc0/src/Order/Order.php#L187) | Nested calls exist, but the inspected catch is for InvalidMandateException, not a database concurrency error. |
| [iznik-batch/app/Support/TransactionPolicy.php](https://github.com/Freegle/Iznik/blob/7f21922be0fc16c19e50e544272217cb58719459/iznik-batch/app/Support/TransactionPolicy.php#L80) | Retry helper catches outside its transaction; a committing outer caller was not traced. Latent under nesting. |
| [app/Actions/Integrations/StoreWebhookPayload.php](https://github.com/arnaud-ritti/skrum/blob/907105e15e02e0aaf98c6946b528a82f107f303c/app/Actions/Integrations/StoreWebhookPayload.php#L54) | Explicitly rethrows DeadlockException before the general catch. |
| [app/Application/Media/IngestMediaUpload.php](https://github.com/SeanVasey/VA-Studio/blob/dd587603af8330c51eac878331c217802c8b720e/app/Application/Media/IngestMediaUpload.php#L130) | Cleanup preserves files on DeadlockException and rethrows the error. |
| [app/Jobs/Batches/ProcessEUBranchBatchImport.php](https://github.com/tudorr89/info-firme/blob/1dcb375547439c3ee66882c8f779f9f402e854c3/app/Jobs/Batches/ProcessEUBranchBatchImport.php#L41) | Batch transaction error is logged and rethrown. |
| [app/Services/AttendanceChangeService.php](https://github.com/angelitoforbeast/likha-hr/blob/6ab19716336220215d83be1133f23dc41ac11071/app/Services/AttendanceChangeService.php#L406) | At an ambient transaction, returns DB::transaction directly; the retry catch is only at the root. |
| [app/DataMapper/Tax/BaseRule.php](https://github.com/invoiceninja/invoiceninja/blob/15ea35ea63f367eba33c04b7acd9ab1227853537/app/DataMapper/Tax/BaseRule.php#L236) | Database-error catch is gated by transactionLevel() == 0. |
| [app/Traits/ModelTrait.php](https://github.com/blotcnm-dev/cms-tenant/blob/753215908dc1c7e5f42a1e7a335a7705d6cbe043/app/Traits/ModelTrait.php#L346) | Manual transaction wrapper and QueryException catches; no established caught nested managed unit. |
| [app/Models/AbstractModel.php](https://github.com/kuaifan/dootask/blob/a2b3a0b30f58cfda4afa967789c164b58600d00c/app/Models/AbstractModel.php#L356) | Explicit begin/commit wrapper; error path attempts rollback then throws. |
| [app/Services/GeoFlow/ArticleSlugRegistry.php](https://github.com/yaojingang/GEOFlow/blob/25e42f079f780e005df52fce5fe01b6c5b71408b/app/Services/GeoFlow/ArticleSlugRegistry.php#L63) | Catch outside transaction rethrows or converts to a validation error. |

## HikariCP F-H2

| File at commit | Inspection |
| --- | --- |
| [Backend/src/main/java/com/capibaracode/backend/config/tenancity/MultitenantConnectionProvider.java](https://github.com/TigselemaAlex/Facturacion/blob/3bc690dc30c950b8650a36fbc52323144ab6fb83/Backend/src/main/java/com/capibaracode/backend/config/tenancity/MultitenantConnectionProvider.java#L33) | Direct setSchema on acquire and release; no dirty isolation/read-only reset established. |
| [Core/Domibus-MSH/src/main/java/eu/domibus/core/jpa/DomibusMultiTenantConnectionProvider.java](https://github.com/nordic-institute/harmony-access-point/blob/1b7474470d66cbf15febfc3187374c0770417b72/Core/Domibus-MSH/src/main/java/eu/domibus/core/jpa/DomibusMultiTenantConnectionProvider.java#L71) | Sets isolation and autoCommit on acquire; schema delegates to helper. Its implementation/pool settings were not traced. |
| [src/main/java/com/hrm/shared/tenancy/SchemaMultiTenantConnectionProvider.java](https://github.com/vjsc-125/hrm-be/blob/53d2d2464c8482b874885ecf3c6669debc48ec1a/src/main/java/com/hrm/shared/tenancy/SchemaMultiTenantConnectionProvider.java#L54) | Schema helper executes SQL through a Statement; this is tracked work, not the missed setSchema API call. |
| [consumer/src/main/java/com/sus/fiap/consumer/config/MultiTenancyConfig.java](https://github.com/jc-perroni/healthcare-queue-system-consumer/blob/aa83f7b7b7099956b2a0d62cb692aeba887b567c/consumer/src/main/java/com/sus/fiap/consumer/config/MultiTenancyConfig.java#L79) | Direct setSchema, best-effort release reset; no dirty isolation/read-only combination established. |
| [src/main/java/com/example/multitenants/config/database/tenant/TenantDatabaseConfig.java](https://github.com/yuhbigd/multi-tenant/blob/d8fb77704b75e8698a3be7eaacec73ad1775ebfd/src/main/java/com/example/multitenants/config/database/tenant/TenantDatabaseConfig.java#L128) | Direct setSchema on acquire; no full failed-reset path established. |
| [backend/payroll-service/src/main/java/com/axonrh/payroll/config/MultiTenantConfig.java](https://github.com/jdeveloperweb/axonrh/blob/90053115b36983d55eca4f95f3bb0731ff91f3bb/backend/payroll-service/src/main/java/com/axonrh/payroll/config/MultiTenantConfig.java#L59) | Direct setSchema on acquire/release; no full failed-reset path established. |

## PDO catch trigger

| File at commit | Inspection |
| --- | --- |
| [app/Actions/Discovery/PromoteCandidate.php](https://github.com/AthenaNetworks/mymate/blob/2d75a4d3c6f7073b557977ff7b45527db9dfc228/app/Actions/Discovery/PromoteCandidate.php#L61) | Nested savepoint; catches only QueryException and rethrows non-23505 errors. |
| [app/Services/Game/SlugService.php](https://github.com/StarCitizenWiki/API/blob/fab953d20b6d6c485c2430066e0a03a7db6fbbb6/app/Services/Game/SlugService.php#L43) | Unique-conflict retry surrounds its own transaction/savepoint. |
| [app/Services/ContentRequestService.php](https://github.com/m3ue/m3u-editor/blob/996693c59fd3eb59d1d987915ad826f13eba63f3/app/Services/ContentRequestService.php#L338) | Insert has its own transaction/savepoint; only unique conflicts are swallowed. |
| [app/Http/Controllers/Api/V1/DomainController.php](https://github.com/nemerald-voip/fspbx/blob/122c3eccac74781253dfe12c63478a9c53589adc/app/Http/Controllers/Api/V1/DomainController.php#L286) | Catch is outside the domain transaction. |
| [app/Services/CheckinCsvImporter.php](https://github.com/shikorism/tissue/blob/34e63261f6086eea1a791a26e7b50fb68d91dda5/app/Services/CheckinCsvImporter.php#L112) | Explicit rollback in both database and general catches. |
| [app/Services/GeoFlow/TitleGenerationCoordinator.php](https://github.com/yaojingang/GEOFlow/blob/25e42f079f780e005df52fce5fe01b6c5b71408b/app/Services/GeoFlow/TitleGenerationCoordinator.php#L133) | Catch is outside transaction and rethrows/converts the unique conflict. |
| [database/migrations/2026_08_28_000100_backfill_title_fingerprints.php](https://github.com/yaojingang/GEOFlow/blob/25e42f079f780e005df52fce5fe01b6c5b71408b/database/migrations/2026_08_28_000100_backfill_title_fingerprints.php#L49) | Retry catches outside each transaction. |
| [Classes/EventStore/Storage/Doctrine/DoctrineEventStorage.php](https://github.com/neos/Neos.EventSourcing/blob/c34ad2bed1f80ac7f853abb359f0aa7a295a1bc3/Classes/EventStore/Storage/Doctrine/DoctrineEventStorage.php#L132) | Rollback before retry or rethrow; commit follows only the successful try. |
| [lib/private/DB/Connection.php](https://github.com/nextcloud/server/blob/f37e65fdebf2cd86ec0119b0971d4143d79c8b44/lib/private/DB/Connection.php#L428) | Query wrappers log and rethrow; commit delegates to DBAL. No silent caller established. |
| [src/DoctrineEventStoreAdapter.php](https://github.com/prooph/event-store-doctrine-adapter/blob/2bb7442f58fd5269869b580044e27f92eba0a035/src/DoctrineEventStoreAdapter.php#L124) | Unique error is converted and rethrown. |
| [lib/Database/ez_pdo.php](https://github.com/ezSQL/ezsql/blob/8a7b568801ef4f62566b1e02c2481b3d14cdea75/lib/Database/ez_pdo.php#L360) | Latent PDO wrapper: some exec/query errors are swallowed, commit delegates to PDO; no actual PostgreSQL committing caller traced. |
| [library/Pgsql.php](https://github.com/hunzsig/h-php/blob/e309cd7d177ec944b5a378bea6255a59aca953b1/library/Pgsql.php#L440) | Latent PostgreSQL PDO wrapper: error() call on query failure; caller outcome/transaction use not traced. |
| [lib/DB.php](https://github.com/jbroadway/elefant/blob/2e5d751e9521f1fcf30f964357761c090645d667/lib/DB.php#L311) | Latent PDO wrapper: execute returns false on exception; begin/commit delegate to PDO. No caller ignoring false traced. |
| [app/Http/Controllers/AppRegisterController.php](https://github.com/pixelfed/pixelfed/blob/99462454d0ccecbf2e27dc8a07e56981b329daa6/app/Http/Controllers/AppRegisterController.php#L112) | Mail-error catch rolls back; no caught query-error/commit shape established. |
| [app/Http/Controllers/Api/ApiV1Controller.php](https://github.com/pixelfed/pixelfed/blob/99462454d0ccecbf2e27dc8a07e56981b329daa6/app/Http/Controllers/Api/ApiV1Controller.php#L1756) | Inspected transaction blocks do not swallow query errors; serialization catches are elsewhere. |
| [nexus/Database/NexusDB.php](https://github.com/xiaomlove/nexusphp/blob/31c176acae9dab3da038f72d15629d7c5bbf6eec/nexus/Database/NexusDB.php#L88) | Query error is converted and thrown; transaction delegates to framework. |
| [app/Services/YamlDatabaseService.php](https://github.com/phpvms/phpvms/blob/7a6f7acef6acfc35c5b9e9c3d1e8703a677da4ee/app/Services/YamlDatabaseService.php#L184) | Import write is contained in a transaction/savepoint before its catch. |

## Dramatiq config

| File at commit | Inspection |
| --- | --- |
| [futuramaapi/workers/_dramatiq/_config.py](https://github.com/koldakov/futuramaapi/blob/b6ea62fb18cb60560c5577e94aed586be1203748/futuramaapi/workers/_dramatiq/_config.py#L9) | Redis broker keeps default middleware and adds AsyncIO/CurrentMessage; Retries retained. |
| [fittrackee/dramatiq_broker.py](https://github.com/SamR1/FitTrackee/blob/9ff0bc0412ea3f687e153d027444a50aedb44a75/fittrackee/dramatiq_broker.py#L50) | Explicit Retries. Config selects Redis outside tests; pyproject pins 2.2.1. |
| [funboost/assist/dramatiq_helper.py](https://github.com/ydf0509/funboost/blob/2b866e55c8a036185a97b558fac29f139ccb50e4/funboost/assist/dramatiq_helper.py#L10) | Redis broker constructed with defaults; integration library, not deployment evidence. |
| [api/infrastructure/dramatiq.py](https://github.com/aai-labs/agent-barn/blob/34b2cd9ef21000dfca8240a9944bcff729537133/api/infrastructure/dramatiq.py#L7) | Redis broker constructed with default middleware. |
| [sbomify/dramatiq_broker.py](https://github.com/sbomify/sbomify/blob/59980543cd366461461f7a46ca09e41566d7dc20/sbomify/dramatiq_broker.py#L33) | settings.py explicitly selects this Redis subclass and Retries. Override addresses F2/F3/F4, not retry hook F1. |
| [server/polar/worker/_broker.py](https://github.com/polarsource/polar/blob/b116f66b91dd135a4554623c08018ea933cc1234/server/polar/worker/_broker.py#L272) | Explicit Retries with Redis subclass; pyproject uses frankie567/dramatiq fork. Upstream F1 exposure NOT verified. |
| [src/tasks/worker.py](https://github.com/bakrianoo/fastapi-ignite/blob/c253607884fe86f9001d01ac911f901ea3a51d98/src/tasks/worker.py#L18) | Explicit Retries(max_retries=3) with Redis. |
| [src/bitcaster/runner/broker.py](https://github.com/bitcaster-io/bitcaster/blob/fec2bc8347d5445d62d899551ab3ba388419f1c2/src/bitcaster/runner/broker.py#L8) | Explicit Retries(max_retries=5) with Redis. |
| [api_dramatiq/broker.py](https://github.com/murrple-1/rss_temple/blob/0a208d36fbf63605f65d24d342d0783af116d32e/api_dramatiq/broker.py#L23) | Explicit Retries; URL chooses Redis/Valkey branch by default, RabbitMQ optional. |
| [backend/wallet/config.py](https://github.com/diem/reference-wallet/blob/e8efec4acc6af6e319cf075c10693ddf7754cc83/backend/wallet/config.py#L51) | Explicit middleware list has only Results; replaces defaults and omits Retries. |
| [vasp/backend/merchant_vasp/config.py](https://github.com/diem/reference-merchant/blob/fa35960cadaa09f7ea4a34c103e0c85fbf71728c/vasp/backend/merchant_vasp/config.py#L32) | Explicit middleware list has only Results; omits Retries. Reference application. |
| [backend/app/worker.py](https://github.com/Subodh7976/Zynapse/blob/1c41fecef013e31c91ac6552b308231c2c3af497/backend/app/worker.py#L11) | Explicit middleware list has only AsyncIO; omits Retries. |
| [app/tasks.py](https://github.com/pafsmith/url-shrinker/blob/7774d93c88e4a00df1c4168219043f1befcf7bba/app/tasks.py#L8) | Explicit middleware list has only AsyncIO; omits Retries. |

## Counts and exclusions

- Laravel: **0 of 16** inspected eligible files establish the complete caught nested managed unit plus committing outer caller. Two helpers remain latent. The first ten `laravel-code-07` hits included an `example/` file, a `readme/` file, and SmallRuralDog’s derivative Form implementation; those three are excluded, leaving seven, plus five `laravel-code-10` files and four `l-txlevel` files. An exception caught outside the visible transaction is not proof of safe behavior under an untraced outer caller.
- HikariCP: **4 of 6** eligible application/provider files directly call JDBC `Connection.setSchema`; **0 of 6** establish the complete failed-reset trigger. The other two use SQL or an untraced schema helper. From twelve `hikari-code-08` hits, exclude two Hibernate interface/settings files, three example/PoC files, and the Kolanot Domibus fork as an independent exposure. `hikari-code-07` configuration/wrapper hits were supporting reads, not additional exposure counts.
- PDO: **0 of 17** eligible inspected files establish a silent PostgreSQL application commit after an uncontained query error; **three** PDO wrappers are latent. Seven `pdo-code-08` files (excluding the compatibility-test script), three relevant `pdo-code-09` files (excluding Mysqli/Sqlsrv drivers), three PDO wrappers from `pdo-code-07`, and four `php-pg-catch` files. Five other `pdo-code-07` hits use native pgsql/pg_wrapper, SQL COMMIT through a different DBAL, or separate connections; they are excluded from the PDO::commit exposure denominator. Additional `pdo-code-10` phpvms migration reads confirm savepoint handling and are supporting counterevidence, not added to the denominator.
- Dramatiq: **9 of 13** unique inspected broker configurations retain or explicitly include Retries; one of those nine (Polar) uses an uninspected fork. **Eight of 13** have upstream-compatible Redis/Retry configuration by source reading; this is potential exposure, not eight failures. Four explicitly replace defaults without Retries. sbomify’s Retries is established by its settings file. Merge FitTrackee’s duplicate search hit; exclude framework copies, virtual environments, a harvested code copy and Sentry’s integration from adoption counts. Diem’s two reference applications are identified as such, not counted as production deployments.
- Four `l-rollback-on` configuration files were read: **4 of 4** enable rollback-on-timeout. They are counterexamples to assuming every deployment uses OFF, not evidence about Laravel deployment prevalence. They belong to OneBlog, UNA, DanWin hosting and a SQL configuration reference; none was established as a Laravel deployment.
