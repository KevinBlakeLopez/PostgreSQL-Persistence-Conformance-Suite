<?php

declare(strict_types=1);

namespace Ppcs;

/** An application failure inside a transaction. Not a database error. */
final class AppException extends \RuntimeException
{
}
