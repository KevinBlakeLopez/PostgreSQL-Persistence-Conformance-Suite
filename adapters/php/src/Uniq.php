<?php

declare(strict_types=1);

namespace Ppcs;

use Illuminate\Database\Eloquent\Model;

/** The runner's uniq table. The fixture already contains code "taken". */
final class Uniq extends Model
{
    protected $table = 'uniq';

    public $timestamps = false;

    protected $guarded = [];
}
