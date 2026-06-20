#include <arpa/inet.h>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

using namespace std;

constexpr int PORT = 8080;
constexpr size_t BUFFER_SIZE = 4096;

uint64_t to_network64(uint64_t value) {
    static const int num = 42;
    const bool little_endian = *reinterpret_cast<const char *>(&num) == 42;

    if (!little_endian) {
        return value;
    }

    uint64_t result = 0;
    for (int i = 0; i < 8; ++i) {
        result = (result << 8) | (value & 0xff);
        value >>= 8;
    }
    return result;
}

bool send_all(int socket_fd, const void *data, size_t length) {
    const char *buffer = static_cast<const char *>(data);
    size_t sent_total = 0;

    while (sent_total < length) {
        ssize_t sent = send(socket_fd, buffer + sent_total, length - sent_total, 0);
        if (sent <= 0) {
            return false;
        }
        sent_total += static_cast<size_t>(sent);
    }

    return true;
}

int main(int argc, char *argv[]) {
    if (argc < 2 || argc > 3) {
        cerr << "Usage: " << argv[0] << " <file_path> [server_ip]\n";
        return 1;
    }

    const filesystem::path file_path = argv[1];
    const string server_ip = argc == 3 ? argv[2] : "127.0.0.1";
    const string file_name = file_path.filename().string();

    if (file_name.empty()) {
        cerr << "error: invalid file path\n";
        return 1;
    }

    ifstream file(file_path, ios::binary);
    if (!file.is_open()) {
        cerr << "error: unable to open file: " << file_path << "\n";
        return 1;
    }

    const uint64_t file_size = filesystem::file_size(file_path);
    const uint32_t file_name_size = static_cast<uint32_t>(file_name.size());

    int client_socket = socket(AF_INET, SOCK_STREAM, 0);
    if (client_socket < 0) {
        perror("socket");
        return 1;
    }

    sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);

    if (inet_pton(AF_INET, server_ip.c_str(), &server_addr.sin_addr) <= 0) {
        cerr << "error: invalid server IP address: " << server_ip << "\n";
        close(client_socket);
        return 1;
    }

    cout << "connecting to " << server_ip << ":" << PORT << "...\n";
    if (connect(client_socket, reinterpret_cast<sockaddr *>(&server_addr), sizeof(server_addr)) < 0) {
        perror("connect");
        close(client_socket);
        return 1;
    }

    const uint32_t network_name_size = htonl(file_name_size);
    const uint64_t network_file_size = to_network64(file_size);

    if (!send_all(client_socket, &network_name_size, sizeof(network_name_size)) ||
        !send_all(client_socket, &network_file_size, sizeof(network_file_size)) ||
        !send_all(client_socket, file_name.data(), file_name.size())) {
        cerr << "error: failed to send file header\n";
        close(client_socket);
        return 1;
    }

    char buffer[BUFFER_SIZE];
    uint64_t total_sent = 0;

    while (file) {
        file.read(buffer, sizeof(buffer));
        streamsize bytes_read = file.gcount();

        if (bytes_read > 0) {
            if (!send_all(client_socket, buffer, static_cast<size_t>(bytes_read))) {
                cerr << "error: failed while sending file contents\n";
                close(client_socket);
                return 1;
            }
            total_sent += static_cast<uint64_t>(bytes_read);
        }
    }

    cout << "sent " << file_name << " (" << total_sent << " bytes)\n";
    close(client_socket);
    return 0;
}
