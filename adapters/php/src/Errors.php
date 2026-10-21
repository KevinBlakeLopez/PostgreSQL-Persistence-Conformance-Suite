<?php

declare(strict_types=1);

namespace Ppcs;

final class Errors
{
    public static function isProtocol(\Throwable $e): bool
    {
        for ($cur = $e; $cur !== null; $cur = $cur->getPrevious()) {
            if ($cur instanceof ProtocolException) {
                return true;
            }
        }

        return false;
    }

    /** @return array{class: string, code: string|null, message: string} */
    public static function info(\Throwable $e): array
    {
        return [
            'class' => $e::class,
            'code' => self::sqlState($e),
            'message' => self::message($e),
        ];
    }

    public static function sqlState(\Throwable $e): ?string
    {
        for ($cur = $e; $cur !== null; $cur = $cur->getPrevious()) {
            if ($cur instanceof \PDOException) {
                $info = $cur->errorInfo ?? null;
                if (is_array($info) && isset($info[0]) && self::isSqlState((string) $info[0])) {
                    return (string) $info[0];
                }
            }
            $code = $cur->getCode();
            if (is_string($code) && self::isSqlState($code)) {
                return $code;
            }
            if (is_int($code) && self::isSqlState((string) $code)) {
                return (string) $code;
            }
        }

        return null;
    }

    public static function message(\Throwable $e): string
    {
        $text = preg_replace('/\s+/', ' ', $e->getMessage()) ?? $e->getMessage();

        return substr($text, 0, 500);
    }

    public static function isSqlState(string $code): bool
    {
        return preg_match('/^[0-9A-Z]{5}$/', $code) === 1;
    }
}
