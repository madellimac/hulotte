#include "MyCustomModule.hpp"

using namespace spu;
using namespace spu::module;

MyCustomModule::MyCustomModule(const int data_size)
: Stateful(), data_size(data_size)
{
    this->set_name("MyCustomModule");
    this->set_short_name("MyCustomModule");

    auto &t = this->create_task("process");
    auto input  = create_socket_in<int>(t, "input", this->data_size);
    auto output = create_socket_out<int>(t, "output", this->data_size);
    
    this->create_codelet(t, [input, output](Module &m, runtime::Task &t, const size_t frame_id) -> int {
        static_cast<MyCustomModule&>(m).process(   static_cast<int*>(t[input].get_dataptr()),
                                                static_cast<int*>(t[output].get_dataptr()),
                                                        frame_id);
        return 0;
    });
}

void MyCustomModule::process(int *in_data, int *out_data, const int frame_id)
{
    // Exemple simple : multiplication par 2
    for (int i = 0; i < this->data_size; i++)
        out_data[i] = in_data[i] * 2;
}
