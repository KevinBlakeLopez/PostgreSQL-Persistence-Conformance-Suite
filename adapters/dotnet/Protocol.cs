using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace Ppcs;

/// <summary>
/// PPCS adapter protocol version 1. Newline-delimited JSON on stdin and stdout.
/// A line is a protocol message only when it has <c>"ppcs": 1</c>.
/// </summary>
public sealed class Protocol
{
    public const int Version = 1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    private readonly StreamReader _input;
    private readonly StreamWriter _output;

    public Protocol()
        : this(Console.OpenStandardInput(), Console.OpenStandardOutput())
    {
    }

    public Protocol(Stream input, Stream output)
    {
        _input = new StreamReader(input, Encoding.UTF8, detectEncodingFromByteOrderMarks: false, bufferSize: 1024, leaveOpen: true);
        _output = new StreamWriter(output, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false), bufferSize: 1024, leaveOpen: true)
        {
            AutoFlush = true,
        };
    }

    /// <summary>Held for the whole checkpoint exchange so two units cannot interleave protocol lines.</summary>
    public object Lock { get; } = new();

    public bool HaltCheckpoints { get; set; }

    public JsonElement Read()
    {
        lock (Lock)
        {
            return ReadUnlocked();
        }
    }

    public void Send(Dictionary<string, object?> message)
    {
        lock (Lock)
        {
            SendUnlocked(message);
        }
    }

    /// <summary>
    /// Report one checkpoint and block until the runner's matching resume.
    /// <paramref name="pid"/> is sent even when null. <paramref name="xid"/> is omitted when unknown.
    /// </summary>
    public JsonElement Checkpoint(string name, string? xid, int? pid, string? isolation = null)
    {
        lock (Lock)
        {
            if (HaltCheckpoints)
            {
                throw new ProtocolException($"checkpoint \"{name}\" was halted");
            }

            var message = new Dictionary<string, object?>
            {
                ["type"] = "checkpoint",
                ["name"] = name,
                ["pid"] = pid,
            };
            if (xid is not null)
            {
                message["xid"] = xid;
            }

            if (isolation is not null)
            {
                message["transaction_isolation"] = isolation;
            }

            SendUnlocked(message);
            var resume = ReadUnlocked();
            var type = resume.TryGetProperty("type", out var typeValue) ? typeValue.GetString() : null;
            var resumeName = resume.TryGetProperty("name", out var nameValue) ? nameValue.GetString() : null;
            if (type != "resume" || resumeName != name)
            {
                throw new ProtocolException($"expected resume for checkpoint \"{name}\"");
            }

            return resume;
        }
    }

    private JsonElement ReadUnlocked()
    {
        while (true)
        {
            var line = _input.ReadLine() ?? throw new ProtocolException("the runner closed the protocol stream");
            line = line.Trim();
            if (line.Length == 0)
            {
                continue;
            }

            JsonDocument document;
            try
            {
                document = JsonDocument.Parse(line);
            }
            catch (JsonException)
            {
                throw new ProtocolException("the runner sent a line that is not JSON");
            }

            using (document)
            {
                var root = document.RootElement;
                if (!root.TryGetProperty("ppcs", out var version) || version.ValueKind != JsonValueKind.Number || version.GetInt32() != Version)
                {
                    continue;
                }

                return root.Clone();
            }
        }
    }

    private void SendUnlocked(Dictionary<string, object?> message)
    {
        message["ppcs"] = Version;
        _output.WriteLine(JsonSerializer.Serialize(message, JsonOptions));
    }
}

public sealed class ProtocolException : Exception
{
    public ProtocolException(string message)
        : base(message)
    {
    }

    public ProtocolException(string message, Exception inner)
        : base(message, inner)
    {
    }
}

public static class CaseJson
{
    public static string Text(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String || value.GetString() is not string text)
        {
            throw new ProtocolException($"the case message is missing string \"{name}\"");
        }

        return text;
    }

    public static string? OptionalText(JsonElement obj, string name)
    {
        if (obj.ValueKind != JsonValueKind.Object || !obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.String)
        {
            return null;
        }

        return value.GetString();
    }

    public static int Int(JsonElement obj, string name, int? fallback = null)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Number)
        {
            if (fallback is int known)
            {
                return known;
            }

            throw new ProtocolException($"the case message is missing number \"{name}\"");
        }

        return value.GetInt32();
    }

    public static JsonElement Object(JsonElement obj, string name)
    {
        if (!obj.TryGetProperty(name, out var value) || value.ValueKind != JsonValueKind.Object)
        {
            throw new ProtocolException($"the case message is missing object \"{name}\"");
        }

        return value;
    }

    public static JsonElement OptionalObject(JsonElement obj, string name)
    {
        if (obj.ValueKind == JsonValueKind.Object && obj.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.Object)
        {
            return value;
        }

        return default;
    }

    public static bool Bool(JsonElement obj, string name, bool fallback = false)
    {
        if (obj.ValueKind != JsonValueKind.Object || !obj.TryGetProperty(name, out var value))
        {
            return fallback;
        }

        return value.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            _ => fallback,
        };
    }
}
