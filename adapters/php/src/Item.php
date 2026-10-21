<?php

declare(strict_types=1);

namespace Ppcs;

use Illuminate\Database\Eloquent\Model;

/** The runner's item table. No timestamps, no hidden attributes. */
final class Item extends Model
{
    protected $table = 'item';

    public $timestamps = false;

    protected $guarded = [];
}
